import random
from typing import Dict, Any, List
from bedwars.models import Player, Team, SHOP_ITEMS

class BotAI:
    @staticmethod
    def decide_action(player: Player, all_players: List[Player], beds_status: Dict[str, bool], difficulty: str = "Easy") -> Dict[str, Any]:
        """
        Decides the bot's action for the turn based on the game difficulty.
        """
        if difficulty == "Hard":
            return BotAI._decide_hard(player, all_players, beds_status)
        elif difficulty == "Medium":
            return BotAI._decide_medium(player, all_players, beds_status)
        else:
            return BotAI._decide_easy(player, all_players, beds_status)

    @staticmethod
    def _decide_easy(player: Player, all_players: List[Player], beds_status: Dict[str, bool]) -> Dict[str, Any]:
        if player.hp <= 12 and player.resources.get("gold", 0) >= 3:
            return {"type": "use_item", "item": "金蘋果"}

        current_loc = player.location
        own_base = f"{player.team.name}基地"
        is_at_own_base = (current_loc == own_base)

        enemies_here = [p for p in all_players if p.is_alive and p.team != player.team and p.location == current_loc]
        bot_seed = sum(ord(c) for c in player.name)
        role_type = bot_seed % 3  # 0: Rusher, 1: Defender, 2: Gatherer

        if "基地" in current_loc and not is_at_own_base:
            enemy_team_name = current_loc.replace("基地", "")
            if not beds_status.get(enemy_team_name, True):
                return {"type": "attack_bed", "target_team": enemy_team_name}

        if enemies_here:
            target = min(enemies_here, key=lambda p: p.hp)
            return {"type": "attack_player", "target_id": target.id}

        if is_at_own_base:
            purchases = []
            defense_purchases = []
            upgrades = []
            
            # Upgrades
            diamonds = player.resources.get("diamond", 0)
            if diamonds >= 4 and not player.team.sharpness:
                upgrades.append("Sharpness")
                diamonds -= 4
            if diamonds >= 2 and player.team.protection_level < 4:
                upgrades.append("Protection")
                diamonds -= 2
            if diamonds >= 2 and player.team.forge_level < 3:
                upgrades.append("Forge")
                diamonds -= 2

            # Gear (Emeralds)
            emeralds = player.resources.get("emerald", 0)
            if emeralds >= 6 and player.armor != "鑽石防具":
                purchases.append("鑽石防具")
                emeralds -= 6
            if emeralds >= 4 and player.sword != "鑽石劍":
                purchases.append("鑽石劍")
                emeralds -= 4
            if emeralds >= 4:
                purchases.append("終界珍珠")
                emeralds -= 4

            # Gear (Gold)
            gold = player.resources.get("gold", 0)
            if gold >= 12 and player.armor not in ["鐵防具", "鑽石防具"]:
                purchases.append("鐵防具")
                gold -= 12
            if gold >= 7 and player.sword not in ["鐵劍", "鑽石劍"]:
                purchases.append("鐵劍")
                gold -= 7
            if gold >= 3 and "黑曜石" not in player.tools:
                purchases.append("鐵鎬")
                gold -= 3
            if gold >= 4 and role_type == 1 and player.team.bed_defense != "黑曜石":
                defense_purchases.append("黑曜石防禦")
                gold -= 4

            # Gear (Iron)
            iron = player.resources.get("iron", 0)
            if iron >= 40 and player.armor == "皮革防具":
                purchases.append("鎖子甲")
                iron -= 40
            if iron >= 20 and "羊毛" not in player.tools:
                purchases.append("剪刀")
                iron -= 20
            if iron >= 10 and player.sword == "木劍":
                purchases.append("石劍")
                iron -= 10
            if iron >= 10 and "木頭" not in player.tools:
                purchases.append("木斧")
                iron -= 10
                
            if not player.team.bed_broken:
                if iron >= 12 and player.team.bed_defense in ["無", "羊毛"] and role_type == 1:
                    defense_purchases.append("木頭防禦")
                    iron -= 12
                elif iron >= 4 and player.team.bed_defense == "無":
                    defense_purchases.append("羊毛防禦")
                    iron -= 4

            if purchases or defense_purchases or upgrades:
                return {
                    "type": "shop",
                    "purchases": purchases,
                    "defense_purchases": defense_purchases,
                    "upgrades": upgrades
                }

        # Travel / Gather
        locations = ["紅隊基地", "藍隊基地", "綠隊基地", "黃隊基地", "鑽石島 A", "鑽石島 B", "綠寶石中心島"]
        active_enemy_bases = [
            f"{t}基地" for t in ["紅隊", "藍隊", "綠隊", "黃隊"]
            if t != player.team.name and not beds_status.get(t, True)
        ]
        
        if role_type == 0:  # RUSHER
            target_loc = random.choice(active_enemy_bases) if active_enemy_bases else "綠寶石中心島"
        elif role_type == 1:  # DEFENDER
            target_loc = own_base if not player.team.bed_broken and random.random() < 0.70 else random.choice(["鑽石島 A", "鑽石島 B"])
        else:  # GATHERER
            if player.resources.get("diamond", 0) >= 4 or player.resources.get("emerald", 0) >= 4:
                target_loc = own_base
            else:
                target_loc = random.choice(["鑽石島 A", "鑽石島 B", "綠寶石中心島"])

        if current_loc != target_loc:
            return {"type": "move", "target": target_loc}
        else:
            return {"type": "gather"}

    @staticmethod
    def _decide_medium(player: Player, all_players: List[Player], beds_status: Dict[str, bool]) -> Dict[str, Any]:
        # Medium Heuristic: Smart heals, gear locks, and upgrade priorities
        if player.hp <= 14 and player.resources.get("gold", 0) >= 3:
            return {"type": "use_item", "item": "金蘋果"}

        current_loc = player.location
        own_base = f"{player.team.name}基地"
        is_at_own_base = (current_loc == own_base)

        enemies_here = [p for p in all_players if p.is_alive and p.team != player.team and p.location == current_loc]
        bot_seed = sum(ord(c) for c in player.name)
        role_type = bot_seed % 3 # 0: Rusher, 1: Defender, 2: Gatherer

        if "基地" in current_loc and not is_at_own_base:
            enemy_team_name = current_loc.replace("基地", "")
            if not beds_status.get(enemy_team_name, True):
                return {"type": "attack_bed", "target_team": enemy_team_name}

        if enemies_here:
            target = min(enemies_here, key=lambda p: p.hp)
            return {"type": "attack_player", "target_id": target.id}

        if is_at_own_base:
            purchases = []
            defense_purchases = []
            upgrades = []
            
            diamonds = player.resources.get("diamond", 0)
            if diamonds >= 4 and not player.team.sharpness:
                upgrades.append("Sharpness")
                diamonds -= 4
            if diamonds >= 2 and player.team.protection_level < 4:
                upgrades.append("Protection")
                diamonds -= 2
            if diamonds >= 2 and player.team.forge_level < 3:
                upgrades.append("Forge")
                diamonds -= 2

            emeralds = player.resources.get("emerald", 0)
            if emeralds >= 6 and player.armor != "鑽石防具":
                purchases.append("鑽石防具")
                emeralds -= 6
            if emeralds >= 4 and player.sword != "鑽石劍":
                purchases.append("鑽石劍")
                emeralds -= 4
            if emeralds >= 4:
                purchases.append("終界珍珠")
                emeralds -= 4

            gold = player.resources.get("gold", 0)
            if gold >= 12 and player.armor not in ["鐵防具", "鑽石防具"]:
                purchases.append("鐵防具")
                gold -= 12
            if gold >= 7 and player.sword not in ["鐵劍", "鑽石劍"]:
                purchases.append("鐵劍")
                gold -= 7
            if gold >= 3 and "黑曜石" not in player.tools:
                purchases.append("鐵鎬")
                gold -= 3

            iron = player.resources.get("iron", 0)
            if iron >= 40 and player.armor == "皮革防具":
                purchases.append("鎖子甲")
                iron -= 40
            if iron >= 20 and "羊毛" not in player.tools:
                purchases.append("剪刀")
                iron -= 20
            if iron >= 10 and player.sword == "木劍":
                purchases.append("石劍")
                iron -= 10
            if iron >= 10 and "木頭" not in player.tools:
                purchases.append("木斧")
                iron -= 10
                
            if not player.team.bed_broken:
                if iron >= 12 and player.team.bed_defense in ["無", "羊毛"]:
                    defense_purchases.append("木頭防禦")
                    iron -= 12
                elif iron >= 4 and player.team.bed_defense == "無":
                    defense_purchases.append("羊毛防禦")
                    iron -= 4

            if purchases or defense_purchases or upgrades:
                return {
                    "type": "shop",
                    "purchases": purchases,
                    "defense_purchases": defense_purchases,
                    "upgrades": upgrades
                }

        active_enemy_bases = [
            f"{t}基地" for t in ["紅隊", "藍隊", "綠隊", "黃隊"]
            if t != player.team.name and not beds_status.get(t, True)
        ]
        
        has_basic_sword = player.sword != "木劍"
        if not has_basic_sword and is_at_own_base:
            return {"type": "gather"}

        if player.team.bed_broken:
            if player.resources.get("diamond", 0) >= 4 or player.resources.get("emerald", 0) >= 4:
                target_loc = own_base
            else:
                target_loc = random.choice(["鑽石島 A", "鑽石島 B", "綠寶石中心島"])
        else:
            if role_type == 0:  # Rusher
                target_loc = random.choice(active_enemy_bases) if active_enemy_bases else "綠寶石中心島"
            elif role_type == 1:  # Defender
                target_loc = own_base if random.random() < 0.75 else random.choice(["鑽石島 A", "鑽石島 B"])
            else:  # Gatherer
                if player.resources.get("diamond", 0) >= 4 or player.resources.get("emerald", 0) >= 4:
                    target_loc = own_base
                else:
                    target_loc = random.choice(["鑽石島 A", "鑽石島 B", "綠寶石中心島"])

        if current_loc != target_loc:
            return {"type": "move", "target": target_loc}
        else:
            return {"type": "gather"}

    @staticmethod
    def _decide_hard(player: Player, all_players: List[Player], beds_status: Dict[str, bool]) -> Dict[str, Any]:
        # Hard Heuristic: Base defense alert, target elimination prioritisation, tactical fireball use
        current_loc = player.location
        own_base = f"{player.team.name}基地"
        is_at_own_base = (current_loc == own_base)

        enemies_at_base = [p for p in all_players if p.is_alive and p.team != player.team and p.location == own_base]
        if enemies_at_base and not is_at_own_base:
            return {"type": "move", "target": own_base}

        if player.hp <= 14 and player.resources.get("gold", 0) >= 3:
            return {"type": "use_item", "item": "金蘋果"}

        enemies_here = [p for p in all_players if p.is_alive and p.team != player.team and p.location == current_loc]
        bot_seed = sum(ord(c) for c in player.name)
        role_type = bot_seed % 3

        if "基地" in current_loc and not is_at_own_base:
            enemy_team_name = current_loc.replace("基地", "")
            # Find the target enemy team's players to get their team object
            enemy_team_players = [p for p in all_players if p.team.name == enemy_team_name]
            if enemy_team_players:
                enemy_team = enemy_team_players[0].team
                if not enemy_team.bed_broken:
                    if enemy_team.bed_defense_hp > 30 and player.resources.get("iron", 0) >= 40:
                        return {"type": "shop", "purchases": ["火球"], "defense_purchases": [], "upgrades": []}
                    return {"type": "attack_bed", "target_team": enemy_team_name}

        if enemies_here:
            target = min(enemies_here, key=lambda p: p.hp)
            return {"type": "attack_player", "target_id": target.id}

        if is_at_own_base:
            purchases = []
            defense_purchases = []
            upgrades = []
            
            if not player.team.bed_broken and player.team.bed_defense != "黑曜石":
                if player.resources.get("gold", 0) >= 4:
                    defense_purchases.append("黑曜石防禦")
                    player.resources["gold"] -= 4
            
            diamonds = player.resources.get("diamond", 0)
            if diamonds >= 4 and not player.team.sharpness:
                upgrades.append("Sharpness")
                diamonds -= 4
            if diamonds >= 2 and player.team.protection_level < 4:
                upgrades.append("Protection")
                diamonds -= 2
            if diamonds >= 2 and player.team.forge_level < 3:
                upgrades.append("Forge")
                diamonds -= 2

            emeralds = player.resources.get("emerald", 0)
            if emeralds >= 6 and player.armor != "鑽石防具":
                purchases.append("鑽石防具")
                emeralds -= 6
            if emeralds >= 4 and player.sword != "鑽石劍":
                purchases.append("鑽石劍")
                emeralds -= 4
            if emeralds >= 4:
                purchases.append("終界珍珠")
                emeralds -= 4

            gold = player.resources.get("gold", 0)
            if gold >= 12 and player.armor not in ["鐵防具", "鑽石防具"]:
                purchases.append("鐵防具")
                gold -= 12
            if gold >= 7 and player.sword not in ["鐵劍", "鑽石劍"]:
                purchases.append("鐵劍")
                gold -= 7
            if gold >= 3 and "黑曜石" not in player.tools:
                purchases.append("鐵鎬")
                gold -= 3

            iron = player.resources.get("iron", 0)
            if iron >= 40 and player.armor == "皮革防具":
                purchases.append("鎖子甲")
                iron -= 40
            if iron >= 20 and "羊毛" not in player.tools:
                purchases.append("剪刀")
                iron -= 20
            if iron >= 10 and player.sword == "木劍":
                purchases.append("石劍")
                iron -= 10
            if iron >= 10 and "木頭" not in player.tools:
                purchases.append("木斧")
                iron -= 10
                
            if not player.team.bed_broken and not defense_purchases:
                if iron >= 12 and player.team.bed_defense in ["無", "羊毛"]:
                    defense_purchases.append("木頭防禦")
                    iron -= 12
                elif iron >= 4 and player.team.bed_defense == "無":
                    defense_purchases.append("羊毛防禦")
                    iron -= 4

            if purchases or defense_purchases or upgrades:
                # Restore resources deducted for local simulation checks
                for p in purchases:
                    item_type = None
                    for cat in SHOP_ITEMS:
                        if p in SHOP_ITEMS[cat]:
                            item_type = cat
                            break
                    if item_type:
                        cost_type = SHOP_ITEMS[item_type][p]["cost_type"]
                        cost = SHOP_ITEMS[item_type][p]["cost"]
                        player.resources[cost_type] += cost
                for dp in defense_purchases:
                    cost_type = SHOP_ITEMS["defenses"][dp]["cost_type"]
                    cost = SHOP_ITEMS["defenses"][dp]["cost"]
                    player.resources[cost_type] += cost
                for upg in upgrades:
                    if upg == "Sharpness":
                        player.resources["diamond"] += 4
                    elif upg == "Protection":
                        player.resources["diamond"] += 2
                    elif upg == "Forge":
                        player.resources["diamond"] += 2
                        
                return {
                    "type": "shop",
                    "purchases": purchases,
                    "defense_purchases": defense_purchases,
                    "upgrades": upgrades
                }

        if player.team.bed_broken:
            if player.resources.get("diamond", 0) >= 4 or player.resources.get("emerald", 0) >= 4:
                target_loc = own_base
            else:
                target_loc = random.choice(["鑽石島 A", "鑽石島 B", "綠寶石中心島"])
            
            if current_loc != target_loc:
                return {"type": "move", "target": target_loc}
            else:
                return {"type": "gather"}

        broken_alive_enemy_bases = [
            f"{t}基地" for t in ["紅隊", "藍隊", "綠隊", "黃隊"]
            if t != player.team.name and beds_status.get(t, True) and any(p.is_alive and p.team.name == t for p in all_players)
        ]
        
        intact_enemy_bases = [
            f"{t}基地" for t in ["紅隊", "藍隊", "綠隊", "黃隊"]
            if t != player.team.name and not beds_status.get(t, True)
        ]

        if role_type == 0:  # Rusher
            if intact_enemy_bases:
                target_loc = random.choice(intact_enemy_bases)
            elif broken_alive_enemy_bases:
                target_loc = random.choice(broken_alive_enemy_bases)
            else:
                target_loc = "綠寶石中心島"
        else:  # Gatherer & Defender
            if player.resources.get("diamond", 0) >= 4 or player.resources.get("emerald", 0) >= 4:
                target_loc = own_base
            else:
                target_loc = random.choice(["鑽石島 A", "鑽石島 B", "綠寶石中心島"])

        if current_loc != target_loc:
            return {"type": "move", "target": target_loc}
        else:
            return {"type": "gather"}
