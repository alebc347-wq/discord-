import random
import discord
from typing import Dict, List, Set, Optional, Any
from bedwars.models import Team, Player, SHOP_ITEMS, RESOURCE_EMOJIS
from bedwars.ai import BotAI

class BedWarsGame:
    def __init__(self, lobby_id: str, mode: str = "Solo", difficulty: str = "Easy"):
        self.lobby_id: str = lobby_id
        self.mode: str = mode # "Solo" (4 players) or "Doubles" (8 players)
        self.difficulty: str = difficulty # "Easy", "Medium", "Hard"
        self.turn_number: int = 1
        self.game_over: bool = False
        self.winner_team: Optional[Team] = None
        self.battle_logs: List[str] = []
        
        # Initialize Teams
        self.teams: Dict[str, Team] = {
            "紅隊": Team("紅隊", "🔴", 0xFF5555),
            "藍隊": Team("藍隊", "🔵", 0x5555FF),
            "綠隊": Team("綠隊", "🟢", 0x55FF55),
            "黃隊": Team("黃隊", "🟡", 0xFFFF55)
        }
        self.players: List[Player] = []
        self.player_map: Dict[str, Player] = {} # id -> Player

    def add_player(self, id: str, name: str, is_bot: bool = False) -> Optional[Player]:
        # Limit checking
        max_players = 4 if self.mode == "Solo" else 8
        if len(self.players) >= max_players:
            return None
            
        # Determine team assignment (round robin)
        team_names = ["紅隊", "藍隊", "綠隊", "黃隊"]
        assigned_team_name = team_names[len(self.players) % 4]
        team = self.teams[assigned_team_name]
        
        player = Player(id, name, team, is_bot)
        team.players.append(player)
        self.players.append(player)
        self.player_map[id] = player
        return player

    def remove_player(self, id: str) -> bool:
        if id in self.player_map:
            player = self.player_map[id]
            player.team.players.remove(player)
            self.players.remove(player)
            del self.player_map[id]
            return True
        return False

    def fill_with_bots(self):
        max_players = 4 if self.mode == "Solo" else 8
        bot_names = [
            "史蒂夫_電腦", "愛麗絲_電腦", "諾奇_電腦", "海洛布萊恩_電腦",
            "夢境_電腦", "科技_電腦", "斯凱皮_電腦", "葛立安_電腦"
        ]
        random.shuffle(bot_names)
        
        team_names = ["紅隊", "藍隊", "綠隊", "黃隊"]
        team_limit = 1 if self.mode == "Solo" else 2
        
        for name in team_names:
            team = self.teams[name]
            while len(team.players) < team_limit and len(self.players) < max_players:
                bot_name = bot_names.pop()
                bot_id = f"bot_{bot_name.lower()}_{random.randint(100, 999)}"
                
                player = Player(bot_id, bot_name, team, is_bot=True)
                team.players.append(player)
                self.players.append(player)
                self.player_map[bot_id] = player

    @property
    def beds_status(self) -> Dict[str, bool]:
        """Returns True if the bed is broken, False if it is intact."""
        return {name: team.bed_broken for name, team in self.teams.items()}

    def run_bot_actions(self):
        """Invoke AI for all bots to queue their actions."""
        for p in self.players:
            if p.is_alive and p.is_bot:
                p.pending_action = BotAI.decide_action(p, self.players, self.beds_status, self.difficulty)
                p.is_ready = True

    def set_player_action(self, player_id: str, action: Dict[str, Any]):
        if player_id in self.player_map:
            p = self.player_map[player_id]
            if p.is_alive:
                p.pending_action = action
                p.is_ready = True

    def check_ready(self) -> bool:
        """Returns True if all alive players are ready."""
        return all(p.is_ready for p in self.players if p.is_alive)

    def resolve_turn(self):
        """Main turn resolution engine. Resolves shopping, movement, combat, bed break, and respawns."""
        self.battle_logs = []
        
        # 1. Spawning resources (based on current locations BEFORE moves resolve)
        for p in self.players:
            if not p.is_alive:
                continue
                
            # Basic resource collection
            multiplier = 2 if p.pending_action and p.pending_action.get("type") == "gather" else 1
            loc = p.location
            
            if "基地" in loc:
                team_name = loc.replace("基地", "")
                team = self.teams[team_name]
                rates = team.generator_rates
                
                iron_amt = int(rates["iron"] * multiplier)
                gold_amt = int(rates["gold"] * multiplier) if random.random() < (rates["gold"] - int(rates["gold"])) or rates["gold"] >= 1.0 else 0
                if rates["gold"] >= 1.0:
                    gold_amt = int(rates["gold"] * multiplier)
                
                p.add_resources("iron", iron_amt)
                if gold_amt > 0:
                    p.add_resources("gold", gold_amt)
                    
                # Emerald generator for level 3 forge
                if rates["emerald"] > 0:
                    em_amt = int(rates["emerald"] * multiplier) if random.random() < rates["emerald"] else 0
                    if em_amt > 0:
                        p.add_resources("emerald", em_amt)
                        
            elif "鑽石" in loc:
                p.add_resources("diamond", 1 * multiplier)
            elif "綠寶石" in loc or "中心" in loc:
                p.add_resources("emerald", 1 * multiplier)

        # Helper attributes for items purchased on this turn
        fireballs_to_throw = [] # list of (player, target_location)
        golden_apples_to_eat = [] # list of players

        # 2. Resolve Shop Purchases
        for p in self.players:
            if not p.is_alive or not p.pending_action:
                continue
                
            action = p.pending_action
            if action.get("type") == "shop":
                # Upgrades
                for upg in action.get("upgrades", []):
                    if upg == "Sharpness" and p.resources.get("diamond", 0) >= 4 and not p.team.sharpness:
                        p.resources["diamond"] -= 4
                        p.team.sharpness = True
                        self.battle_logs.append(f"✨ {p.team.emoji} **{p.name}** 購買了團隊升級：**鋒利**！")
                    elif upg == "Protection" and p.resources.get("diamond", 0) >= 2 and p.team.protection_level < 4:
                        p.resources["diamond"] -= 2
                        p.team.protection_level += 1
                        self.battle_logs.append(f"🛡️ {p.team.emoji} **{p.name}** 將團隊**保護**升級至等級 {p.team.protection_level}！")
                    elif upg == "Forge" and p.resources.get("diamond", 0) >= 2 and p.team.forge_level < 3:
                        p.resources["diamond"] -= 2
                        p.team.forge_level += 1
                        self.battle_logs.append(f"⚙️ {p.team.emoji} **{p.name}** 將團隊**資源熔爐**升級至等級 {p.team.forge_level}！")

                # Bed Defenses
                for df in action.get("defense_purchases", []):
                    details = SHOP_ITEMS["defenses"].get(df)
                    if details and p.resources.get(details["cost_type"], 0) >= details["cost"]:
                        p.resources[details["cost_type"]] -= details["cost"]
                        p.team.bed_defense = details["type"]
                        p.team.bed_defense_hp = details["hp"]
                        self.battle_logs.append(f"🛏️ {p.team.emoji} **{p.name}** 為團隊購買了 **{details['type']}**！")

                # Gear / Tools / Utilities
                for item_name in action.get("purchases", []):
                    category = None
                    for cat in ["weapons", "armor", "tools", "utilities"]:
                        if item_name in SHOP_ITEMS[cat]:
                            category = cat
                            break
                            
                    if not category:
                        continue
                        
                    details = SHOP_ITEMS[category][item_name]
                    if p.resources.get(details["cost_type"], 0) >= details["cost"]:
                        p.resources[details["cost_type"]] -= details["cost"]
                        
                        if category == "weapons":
                            p.sword = item_name
                            self.battle_logs.append(f"⚔️ {p.team.emoji} **{p.name}** 購買了 **{item_name}**。")
                        elif category == "armor":
                            p.armor = item_name
                            self.battle_logs.append(f"🛡️ {p.team.emoji} **{p.name}** 購買了 **{item_name}**。")
                        elif category == "tools":
                            p.tools.add(details["target"])
                            self.battle_logs.append(f"🛠️ {p.team.emoji} **{p.name}** 購買了工具：**{item_name}**。")
                        elif category == "utilities":
                            if item_name == "金蘋果":
                                golden_apples_to_eat.append(p)
                            elif item_name == "火球":
                                target_choices = [loc for loc in ["紅隊基地", "藍隊基地", "綠隊基地", "黃隊基地", "鑽石島 A", "鑽石島 B", "綠寶石中心島"] if loc != p.location]
                                target_loc = random.choice(target_choices) if target_choices else p.location
                                fireballs_to_throw.append((p, target_loc))
                            elif item_name == "終界珍珠":
                                self.battle_logs.append(f"🔮 {p.team.emoji} **{p.name}** 購買了 **終界珍珠**。")

        # Resolve instant items like Golden Apples
        for p in golden_apples_to_eat:
            p.hp = min(p.max_hp, p.hp + 8)
            self.battle_logs.append(f"🍎 {p.team.emoji} **{p.name}** 吃了 **金蘋果**，恢復了 8 點生命值！(HP: {p.hp}/{p.max_hp})")

        # Resolve instant action: eating a golden apple if they used it as their main action
        for p in self.players:
            if p.is_alive and p.pending_action and p.pending_action.get("type") == "use_item":
                item_name = p.pending_action.get("item")
                if item_name == "金蘋果":
                    if p.resources.get("gold", 0) >= 3:
                        p.resources["gold"] -= 3
                        p.hp = min(p.max_hp, p.hp + 8)
                        self.battle_logs.append(f"🍎 {p.team.emoji} **{p.name}** 購買並使用了 **金蘋果**！(HP: {p.hp}/{p.max_hp})")

        # Resolve Fireballs
        for p, target_loc in fireballs_to_throw:
            self.battle_logs.append(f"☄️ {p.team.emoji} **{p.name}** 向 **{target_loc}** 投擲了 **火球**！")
            target_players = [tgt for tgt in self.players if tgt.is_alive and tgt.location == target_loc]
            for tp in target_players:
                dmg = 5
                dmg_taken = int(dmg * (1 - tp.armor_reduction))
                dmg_taken = max(1, dmg_taken)
                tp.hp -= dmg_taken
                self.battle_logs.append(f"  💥 **{tp.name}** 被爆炸波及，受到了 {dmg_taken} 點傷害！(HP: {tp.hp}/{tp.max_hp})")
            
            if "基地" in target_loc:
                target_team_name = target_loc.replace("基地", "")
                target_team = self.teams[target_team_name]
                if not target_team.bed_broken and target_team.bed_defense_hp > 0:
                    reduction = 20
                    target_team.bed_defense_hp = max(0, target_team.bed_defense_hp - reduction)
                    self.battle_logs.append(f"  🛏️ **{target_team_name}隊** 的床防禦值降低了 {reduction} HP！(剩餘：{target_team.bed_defense_hp})")
                    if target_team.bed_defense_hp == 0:
                        target_team.bed_defense = "無"
                        self.battle_logs.append(f"  🔥 **{target_team_name}隊 的床防禦** 被完全摧毀！")

        # 3. Resolve Movement Actions
        for p in self.players:
            if not p.is_alive or not p.pending_action:
                continue
                
            action = p.pending_action
            if action.get("type") == "move":
                dest = action.get("target")
                old_loc = p.location
                
                has_pearl = "終界珍珠" in action.get("purchases", [])
                
                # Check void fall chance based on difficulty
                void_chance = 0.05
                if p.is_bot:
                    if self.difficulty == "Medium":
                        void_chance = 0.03
                    elif self.difficulty == "Hard":
                        void_chance = 0.01
                
                if not has_pearl and random.random() < void_chance:
                    p.hp = 0
                    p.deaths += 1
                    self.battle_logs.append(f"🌌 {p.team.emoji} **{p.name}** 在從 **{old_loc}** 搭橋移動時失足，掉入了**虛空**！")
                    self._drop_resources(p)
                else:
                    p.location = dest
                    self.battle_logs.append(f"🏃 {p.team.emoji} **{p.name}** 從 **{old_loc}** 移動到了 **{dest}**。")

        # 4. Resolve Combat (Attack Player)
        damages_to_apply = [] # list of (target_player, damage, attacker_player)
        for p in self.players:
            if not p.is_alive or not p.pending_action:
                continue
                
            action = p.pending_action
            if action.get("type") == "attack_player":
                target_id = action.get("target_id")
                target = self.player_map.get(target_id)
                
                if target and target.is_alive and target.location == p.location:
                    raw_dmg = p.sword_damage
                    dmg_taken = int(raw_dmg * (1 - target.armor_reduction))
                    dmg_taken = max(1, dmg_taken)
                    damages_to_apply.append((target, dmg_taken, p))
                else:
                    self.battle_logs.append(f"⚔️ {p.team.emoji} **{p.name}** 企圖發起攻擊，但目標不在此處。")

        # Apply damage
        for target, dmg, attacker in damages_to_apply:
            if not target.is_alive:
                continue
            target.hp -= dmg
            self.battle_logs.append(f"⚔️ {attacker.team.emoji} **{attacker.name}** 使用 **{attacker.sword}** 擊中 {target.team.emoji} **{target.name}**，造成 **{dmg}** 點傷害！(HP: {target.hp}/{target.max_hp})")
            
            if target.hp <= 0:
                target.hp = 0
                target.deaths += 1
                attacker.kills += 1
                
                looted_resources = []
                for res, amt in target.resources.items():
                    if amt > 0:
                        attacker.add_resources(res, amt)
                        looted_resources.append(f"{RESOURCE_EMOJIS[res]}{amt}")
                        
                if not target.team.bed_broken:
                    self.battle_logs.append(f"💀 {target.team.emoji} **{target.name}** 被 {attacker.team.emoji} **{attacker.name}** 擊殺了！")
                else:
                    self.battle_logs.append(f"⚡ **[最終擊殺]** {target.team.emoji} **{target.name}** 被 {attacker.team.emoji} **{attacker.name}** 徹底消滅！")
                
                if looted_resources:
                    self.battle_logs.append(f"🎒 {attacker.name} 搜刮了 {target.name} 的屍體，獲得了：" + ", ".join(looted_resources))
                
                self._drop_resources(target)

        # 5. Resolve Bed Attacks (Bed Breaking)
        for p in self.players:
            if not p.is_alive or not p.pending_action:
                continue
                
            action = p.pending_action
            if action.get("type") == "attack_bed":
                target_team_name = action.get("target_team")
                target_team = self.teams.get(target_team_name)
                
                if target_team and p.location == f"{target_team.name}基地":
                    if target_team.bed_broken:
                        continue
                        
                    if target_team.bed_defense_hp > 0:
                        break_dmg = 5
                        defense_type = target_team.bed_defense
                        
                        if defense_type == "羊毛" and "羊毛" in p.tools:
                            break_dmg = 30
                        elif defense_type == "木頭" and "木頭" in p.tools:
                            break_dmg = 30
                        elif defense_type == "黑曜石" and "黑曜石" in p.tools:
                            break_dmg = 40
                            
                        target_team.bed_defense_hp -= break_dmg
                        self.battle_logs.append(f"🛏️ {p.team.emoji} **{p.name}** 攻擊了 **{target_team_name}的床防禦** ({defense_type})，造成 **{break_dmg}** 點傷害！(剩餘 HP: {max(0, target_team.bed_defense_hp)})")
                        
                        if target_team.bed_defense_hp <= 0:
                            target_team.bed_defense_hp = 0
                            target_team.bed_defense = "無"
                            self.battle_logs.append(f"🔥 **{target_team_name}隊** 的床防禦被**打破**了！")
                    else:
                        # Bed is broken!
                        target_team.bed_broken = True
                        p.bed_breaks += 1
                        self.battle_logs.append(f"🚨🚨 **[床位破壞]** **{target_team_name}的床**被 {p.team.emoji} **{p.name}** **摧毀**了！他們將無法再復活！")
                else:
                    self.battle_logs.append(f"🛏️ {p.team.emoji} **{p.name}** 企圖攻擊 {target_team_name} 的床，但本人並不在該隊基地。")

        # 6. Respawn / Death Resolutions
        for p in self.players:
            if not p.is_alive:
                if not p.team.bed_broken:
                    p.reset_inventory()
                    self.battle_logs.append(f"♻️ {p.team.emoji} **{p.name}** 在基地復活（床完好無損）。")
                else:
                    self.battle_logs.append(f"❌ {p.team.emoji} **{p.name}** 被**最終擊殺**，淘汰出局（床已毀壞）。")

        # 7. Check Game Over Conditions
        alive_teams = set()
        for p in self.players:
            if p.is_alive or not p.team.bed_broken:
                alive_teams.add(p.team.name)
                
        if len(alive_teams) == 1:
            self.game_over = True
            winning_team_name = list(alive_teams)[0]
            self.winner_team = self.teams[winning_team_name]
            self.battle_logs.append(f"🏆🎉 **{winning_team_name}** 贏得了這場比賽！")
        elif len(alive_teams) == 0:
            self.game_over = True
            self.battle_logs.append("⚔️ 驟死賽：沒有隊伍存活！遊戲以和局結束。")
            
        if self.turn_number >= 40 and not self.game_over:
            # Sudden death at turn 40 (destroy all beds!)
            for team in self.teams.values():
                if not team.bed_broken:
                    team.bed_broken = True
                    self.battle_logs.append(f"⏰ **驟死賽！** {team.name}的床因時間超時被自動摧毀！")

        # Increment turn number and reset actions
        self.turn_number += 1
        for p in self.players:
            p.pending_action = None
            p.is_ready = False

    def _drop_resources(self, player: Player):
        """Reset player state to dead, dropping inventory resources."""
        player.is_alive = False
        player.resources = {"iron": 0, "gold": 0, "diamond": 0, "emerald": 0}

    def draw_ascii_map(self) -> str:
        """Draws a premium dynamic text map displaying players at each location."""
        p_at = {}
        for loc in ["紅隊基地", "藍隊基地", "綠隊基地", "黃隊基地", "鑽石島 A", "鑽石島 B", "綠寶石中心島"]:
            p_at[loc] = [p.team.emoji for p in self.players if p.is_alive and p.location == loc]
        
        def format_node(loc, default_name):
            emojis = "".join(p_at[loc])
            if emojis:
                return f"{default_name}({emojis})"
            return default_name
            
        red = format_node("紅隊基地", "紅隊基地")
        blue = format_node("藍隊基地", "藍隊基地")
        green = format_node("綠隊基地", "綠隊基地")
        yellow = format_node("黃隊基地", "黃隊基地")
        dia_a = format_node("鑽石島 A", "鑽石 A")
        dia_b = format_node("鑽石島 B", "鑽石 B")
        mid = format_node("綠寶石中心島", "中心島")
        
        map_str = (
            f"          [{red}]\n"
            f"               │\n"
            f"[{green}] ── [{dia_a}] ── [{mid}] ── [{dia_b}] ── [{yellow}]\n"
            f"               │\n"
            f"          [{blue}]"
        )
        return map_str

    def format_map_status(self) -> str:
        """Returns a string listing who is at which location."""
        locations = {
            "紅隊基地": [],
            "藍隊基地": [],
            "綠隊基地": [],
            "黃隊基地": [],
            "鑽石島 A": [],
            "鑽石島 B": [],
            "綠寶石中心島": []
        }
        
        for p in self.players:
            if p.is_alive:
                locations[p.location].append(f"{p.team.emoji}`{p.name}` (HP:{p.hp})")
                
        lines = []
        for loc, players_here in locations.items():
            players_str = ", ".join(players_here) if players_here else "*空無一人*"
            
            # Add bed stats for base locations
            bed_str = ""
            if "基地" in loc:
                team_name = loc.replace("基地", "")
                team = self.teams[team_name]
                if team.bed_broken:
                    bed_str = " (🛏️ ❌)"
                else:
                    defense_name = team.bed_defense
                    defense_hp = team.bed_defense_hp
                    bed_str = f" (🛏️ 防禦: {defense_name} [{defense_hp} HP])"
                    
            lines.append(f"📍 **{loc}**{bed_str}\n   └─ {players_str}")
            
        return "\n".join(lines)

    def create_embed(self, end_timestamp: int = None) -> discord.Embed:
        """Create a beautiful embed showing the current state of the game."""
        if self.game_over:
            embed = discord.Embed(
                title=f"🎮 床戰對決結束！(第 {self.turn_number-1} 回合)",
                description=f"🏆 **獲勝隊伍**: {self.winner_team.emoji} **{self.winner_team.name}**" if self.winner_team else "🤝 **和局**",
                color=self.winner_team.color_code if self.winner_team else 0x555555
            )
        else:
            time_str = f"本回合將在 <t:{end_timestamp}:R> 自動解析！" if end_timestamp else "請點擊下方按鈕選擇您的行動。"
            embed = discord.Embed(
                title=f"🎮 床戰對決 - 第 {self.turn_number} 回合",
                description=f"⚔️ 摧毀敵方的床並擊敗所有玩家！\n⏰ **時間限制**：{time_str}",
                color=0x2F3136
            )
            
        # Battle Logs
        if self.battle_logs:
            logs_content = "\n".join(self.battle_logs[:15]) # limit to 15 logs
            if len(self.battle_logs) > 15:
                logs_content += f"\n*...以及其他 {len(self.battle_logs) - 15} 個事件。*"
            embed.add_field(name="📜 上一回合事件", value=logs_content, inline=False)
            
        # ASCII Map
        embed.add_field(name="🗺️ 戰場即時地圖", value=f"```\n{self.draw_ascii_map()}\n```", inline=False)
        
        # Map State
        embed.add_field(name="📍 區域節點詳情", value=self.format_map_status(), inline=False)
        
        # Player Standings & Inventories
        standings = []
        for p in self.players:
            status_symbol = "🟢" if p.is_alive else "💀"
            bed_symbol = "🛏️" if not p.team.bed_broken else "❌"
            res_str = "".join([f"{RESOURCE_EMOJIS[r]}{p.resources[r]}" for r in ["iron", "gold", "diamond", "emerald"]])
            standings.append(
                f"{status_symbol} {p.team.emoji} **{p.name}** {bed_symbol}\n"
                f"   └─ HP:{p.hp} | {p.sword} | {p.armor} | {res_str}"
            )
        embed.add_field(name="👥 隊員狀態與裝備", value="\n".join(standings), inline=False)
        
        diff_str = "簡單" if self.difficulty == "Easy" else ("普通" if self.difficulty == "Medium" else "困難")
        embed.set_footer(text=f"模式: {'單人' if self.mode == 'Solo' else '雙人'} | 難度: {diff_str} | 大廳: {self.lobby_id}")
        return embed
