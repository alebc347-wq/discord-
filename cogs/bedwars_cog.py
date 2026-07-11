import discord
from discord.ext import commands
from discord import app_commands
import asyncio
from typing import Dict, Any, Optional, List
import uuid
import random
import time

from bedwars.game import BedWarsGame
from bedwars.models import Player, Team, SHOP_ITEMS, RESOURCE_EMOJIS

class BedWarsCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.active_games: Dict[int, BedWarsGame] = {} # channel_id -> BedWarsGame
        self.game_tasks: Dict[int, asyncio.Task] = {} # channel_id -> asyncio.Task for the game loop
        self.lobby_hosts: Dict[int, int] = {} # channel_id -> host_user_id
        self.game_messages: Dict[int, List[discord.Message]] = {} # channel_id -> list of Messages to cleanup

    # 1. Primary Chinese Commands
    @app_commands.command(name="床戰", description="開啟一場新的回合制 Discord 床戰對決！")
    @app_commands.choices(
        mode=[
            app_commands.Choice(name="單人對決 (4 玩家/電腦)", value="Solo"),
            app_commands.Choice(name="雙人對決 (8 玩家/電腦)", value="Doubles")
        ],
        difficulty=[
            app_commands.Choice(name="簡單 (預設)", value="Easy"),
            app_commands.Choice(name="普通", value="Medium"),
            app_commands.Choice(name="困難", value="Hard")
        ]
    )
    async def bedwars_chinese(self, interaction: discord.Interaction, mode: str = "Solo", difficulty: str = "Easy"):
        await self.bedwars_core(interaction, mode, difficulty)

    @app_commands.command(name="床戰幫助", description="顯示床戰遊戲規則與玩法手冊")
    async def bedwars_help(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="📖 回合制床戰（BedWars）玩法指南",
            description="歡迎來到回合制 Discord 床戰！這是一個多人對決與策略模擬遊戲，請閱讀以下指南以迅速上手。",
            color=0x2F3136
        )
        embed.add_field(
            name="🏁 遊戲流程",
            value="1. 輸入 `/床戰` 建立大廳。\n"
                  "2. 在下拉選單中**點選想要的隊伍顏色**加入對決，或點「加入電腦」補滿人數。\n"
                  "3. 點選「開始對決」進入戰場，每回合有 **30 秒** 的行動決策時間。\n"
                  "4. 每回合開始時，系統將依據您的位置發放資源，隨後結算玩家所下的行動。",
            inline=False
        )
        embed.add_field(
            name="🗺️ 地圖結構與資源產量",
            value="- **所屬基地**：每回合生成 +4 鐵，並有機會獲得金幣。可以在此購買裝備、放置床防禦、購買團隊升級。\n"
                  "- **鑽石島 (A & B)**：每回合生成 +1 鑽石。距離基地 1 回合移動距離。\n"
                  "- **綠寶石中心島**：每回合生成 +1 綠寶石。距離鑽石島 1 回合距離。\n"
                  "- **原地防守/收集 (Gather)**：如果選擇原地防守，該回合的資源產量會 **加倍**！",
            inline=False
        )
        embed.add_field(
            name="🛒 鐵匠商店與物價表",
            value="- ⚔️ **武器**：石劍 (10 鐵) 🗡️ 鐵劍 (7 金) 🗡️ 鑽石劍 (4 綠寶石)\n"
                  "- 🛡️ **防具**：鎖子甲 (40 鐵) 🛡️ 鐵防具 (12 金) 🛡️ 鑽石防具 (6 綠寶石)\n"
                  "- 🛠️ **破防工具**：剪刀 (20 鐵，克羊毛) 🪓 木斧 (10 鐵，克木頭) ⛏️ 鐵鎬 (3 金，克黑曜石)\n"
                  "- 🛏️ **床防禦**：羊毛 (4 鐵) 🪵 木頭 (12 鐵) 🧱 黑曜石 (4 金)\n"
                  "- 🍎 **特殊道具**：金蘋果 (3 金，回8生命) 🔮 終界珍珠 (4 綠寶石，傳送防墜) ☄️ 火球 (40 鐵，範圍傷+破壞防禦)",
            inline=False
        )
        embed.add_field(
            name="👑 勝利條件",
            value="前往敵方基地並使用 **💥 攻擊床** 削減其防禦，直至摧毀床。被摧毀床的隊伍將無法復活。擊殺全部敵隊玩家即可獲得勝利！",
            inline=False
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="床戰取消", description="取消當前頻道正在進行的床戰對決")
    async def bedwars_cancel(self, interaction: discord.Interaction):
        channel_id = interaction.channel_id
        if channel_id not in self.active_games:
            await interaction.response.send_message("❌ 當前頻道沒有正在進行的床戰對決。", ephemeral=True)
            return
            
        host_id = self.lobby_hosts.get(channel_id)
        if interaction.user.id != host_id and not interaction.user.guild_permissions.manage_messages:
            await interaction.response.send_message("❌ 只有大廳房主或管理員才能取消對決！", ephemeral=True)
            return
            
        task = self.game_tasks.get(channel_id)
        if task:
            task.cancel()
            
        self.cleanup_game(channel_id)
        await interaction.response.send_message("⚠️ 床戰對決已被手動取消！")

    # 2. English Alias Command
    @app_commands.command(name="bedwars", description="Start a new BedWars simulation game!")
    @app_commands.choices(
        mode=[
            app_commands.Choice(name="Solo (4 Players/Bots)", value="Solo"),
            app_commands.Choice(name="Doubles (8 Players/Bots)", value="Doubles")
        ],
        difficulty=[
            app_commands.Choice(name="Easy (Default)", value="Easy"),
            app_commands.Choice(name="Medium", value="Medium"),
            app_commands.Choice(name="Hard", value="Hard")
        ]
    )
    async def bedwars_english(self, interaction: discord.Interaction, mode: str = "Solo", difficulty: str = "Easy"):
        await self.bedwars_core(interaction, mode, difficulty)

    async def bedwars_core(self, interaction: discord.Interaction, mode: str, difficulty: str):
        channel_id = interaction.channel_id
        
        if channel_id in self.active_games:
            await interaction.response.send_message("❌ 此頻道已有正在進行或正在設定的床戰對決！", ephemeral=True)
            return

        game = BedWarsGame(lobby_id=str(uuid.uuid4())[:8], mode=mode, difficulty=difficulty)
        self.active_games[channel_id] = game
        self.lobby_hosts[channel_id] = interaction.user.id
        self.game_messages[channel_id] = []
        
        # Add host automatically to Red team as default
        game.add_player(str(interaction.user.id), interaction.user.display_name, is_bot=False)
        
        embed = self.create_lobby_embed(game, interaction.user)
        view = LobbyView(self, channel_id)
        
        await interaction.response.send_message(embed=embed, view=view)
        try:
            lobby_msg = await interaction.original_response()
            self.game_messages[channel_id].append(lobby_msg)
        except Exception:
            pass

    # Text Commands (Prefix Commands)
    @commands.group(name="cw", invoke_without_command=True)
    async def cw(self, ctx: commands.Context):
        await ctx.send("💡 請使用 `.cw clear` 來清理頻道中的床戰對決訊息！", delete_after=10)

    @cw.command(name="clear")
    async def cw_clear(self, ctx: commands.Context):
        def is_bot_message(message: discord.Message):
            return message.author.id == self.bot.user.id
            
        try:
            try:
                await ctx.message.delete()
            except Exception:
                pass
                
            deleted = await ctx.channel.purge(limit=100, check=is_bot_message)
            await ctx.send(f"🧹 已成功清理 {len(deleted)} 條機器人對決訊息！", delete_after=5)
        except Exception as e:
            await ctx.send(f"❌ 清理訊息時發生錯誤：{e}", delete_after=10)

    def create_lobby_embed(self, game: BedWarsGame, host: discord.User) -> discord.Embed:
        embed = discord.Embed(
            title="🎮 床戰對決大廳",
            description=f"房主: {host.mention}\n模式: **{'單人' if game.mode == 'Solo' else '雙人'}**\n\n💡 **玩法說明**：點選下拉選單選擇隊伍顏色加入或換隊！點選按鈕補滿電腦即可開始！",
            color=0x2F3136
        )
        
        for team_name, team in game.teams.items():
            max_players = 1 if game.mode == "Solo" else 2
            players_list = []
            for p in team.players:
                bot_tag = " [電腦]" if p.is_bot else ""
                players_list.append(f"└─ 👤 **{p.name}**{bot_tag}")
            
            val = "\n".join(players_list) if players_list else "*空無一人*"
            embed.add_field(
                name=f"{team.emoji} {team_name} ({len(team.players)}/{max_players})",
                value=val,
                inline=True
            )
            
        embed.set_footer(text=f"大廳 ID: {game.lobby_id} | 使用 /床戰幫助 觀看規則說明")
        return embed

    async def run_game_loop(self, channel: discord.TextChannel, game: BedWarsGame):
        channel_id = channel.id
        try:
            while not game.game_over:
                # Calculate relative countdown timestamp (30s)
                end_timestamp = int(time.time() + 30)
                
                embed = game.create_embed(end_timestamp)
                view = GameMainView(self, channel_id)
                
                message = await channel.send(embed=embed, view=view)
                if channel_id in self.game_messages:
                    self.game_messages[channel_id].append(message)
                
                game.run_bot_actions()
                
                timer = 30
                while timer > 0:
                    if game.check_ready():
                        break
                    await asyncio.sleep(1)
                    timer -= 1
                    
                for p in game.players:
                    if p.is_alive and not p.is_ready:
                        p.pending_action = {"type": "gather"}
                        p.is_ready = True
                        
                game.resolve_turn()
                await asyncio.sleep(2)
                
            # Game Over (Post final summary, do not track so it stays in chat)
            embed = game.create_embed()
            await channel.send(embed=embed)
            
        except asyncio.CancelledError:
            await channel.send("⚠️ 床戰對決已被手動取消。")
        except Exception as e:
            await channel.send(f"❌ 遊戲引擎發生錯誤：{e}")
        finally:
            self.cleanup_game(channel_id)

    def cleanup_game(self, channel_id: int):
        if channel_id in self.game_messages:
            msgs = self.game_messages[channel_id].copy()
            del self.game_messages[channel_id]
            asyncio.create_task(self.delete_messages_async(msgs))

        if channel_id in self.active_games:
            del self.active_games[channel_id]
        if channel_id in self.game_tasks:
            del self.game_tasks[channel_id]
        if channel_id in self.lobby_hosts:
            del self.lobby_hosts[channel_id]

    async def delete_messages_async(self, messages: List[discord.Message]):
        for msg in messages:
            try:
                await msg.delete()
                await asyncio.sleep(0.2) # sleep slightly to avoid rate limit
            except Exception:
                pass


# --- LOBBY VIEW ---
class LobbyView(discord.ui.View):
    def __init__(self, cog: BedWarsCog, channel_id: int):
        super().__init__(timeout=180)
        self.cog = cog
        self.channel_id = channel_id
        
        game = cog.active_games.get(channel_id)
        
        # Add Team selection dropdown dynamically
        self.team_select = TeamSelect(game)
        self.add_item(self.team_select)

    @discord.ui.button(label="加入對決", style=discord.ButtonStyle.green, emoji="🎮", row=1)
    async def join_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        game = self.cog.active_games.get(self.channel_id)
        if not game:
            await interaction.response.send_message("❌ 大廳不存在。", ephemeral=True)
            return
            
        if any(p.id == str(interaction.user.id) for p in game.players):
            await interaction.response.send_message("⚠️ 你已在大廳中！", ephemeral=True)
            return
            
        player = game.add_player(str(interaction.user.id), interaction.user.display_name, is_bot=False)
        if not player:
            await interaction.response.send_message("❌ 大廳已滿！", ephemeral=True)
            return
            
        # Refresh select dropdown options
        self.team_select.options = self.team_select.build_options()
        
        host_id = self.cog.lobby_hosts.get(self.channel_id)
        host = interaction.guild.get_member(host_id) or interaction.user
        embed = self.cog.create_lobby_embed(game, host)
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="離開對決", style=discord.ButtonStyle.red, emoji="🚪", row=1)
    async def leave_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        game = self.cog.active_games.get(self.channel_id)
        if not game:
            await interaction.response.send_message("❌ 大廳不存在。", ephemeral=True)
            return
            
        removed = game.remove_player(str(interaction.user.id))
        if not removed:
            await interaction.response.send_message("⚠️ 你不在大廳中！", ephemeral=True)
            return
            
        if len(game.players) == 0:
            self.cog.cleanup_game(self.channel_id)
            await interaction.response.edit_message(content="🚪 玩家已全部離開，大廳關閉。", embed=None, view=None)
            return
            
        host_id = self.cog.lobby_hosts.get(self.channel_id)
        if host_id == interaction.user.id:
            new_host_p = [p for p in game.players if not p.is_bot][0]
            self.cog.lobby_hosts[self.channel_id] = int(new_host_p.id)
            host_id = int(new_host_p.id)
            
        self.team_select.options = self.team_select.build_options()
        
        host = interaction.guild.get_member(host_id)
        embed = self.cog.create_lobby_embed(game, host)
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="加入電腦", style=discord.ButtonStyle.grey, emoji="🤖", row=2)
    async def add_bot_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        game = self.cog.active_games.get(self.channel_id)
        if not game:
            await interaction.response.send_message("❌ 大廳不存在。", ephemeral=True)
            return
            
        max_players = 4 if game.mode == "Solo" else 8
        if len(game.players) >= max_players:
            await interaction.response.send_message("❌ 大廳已滿！", ephemeral=True)
            return
            
        game.fill_with_bots()
        self.team_select.options = self.team_select.build_options()
        
        host_id = self.cog.lobby_hosts.get(self.channel_id)
        host = interaction.guild.get_member(host_id)
        embed = self.cog.create_lobby_embed(game, host)
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="開始對決", style=discord.ButtonStyle.blurple, emoji="⚔️", row=2)
    async def start_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        game = self.cog.active_games.get(self.channel_id)
        if not game:
            await interaction.response.send_message("❌ 大廳不存在。", ephemeral=True)
            return
            
        host_id = self.cog.lobby_hosts.get(self.channel_id)
        if interaction.user.id != host_id:
            await interaction.response.send_message("❌ 只有房主能開始對決！", ephemeral=True)
            return
            
        game.fill_with_bots()
        await interaction.response.edit_message(content="⚔️ **床戰對決開始！正在載入戰場地圖...**", embed=None, view=None)
        
        task = asyncio.create_task(self.cog.run_game_loop(interaction.channel, game))
        self.cog.game_tasks[self.channel_id] = task


class TeamSelect(discord.ui.Select):
    def __init__(self, game: BedWarsGame):
        self.game = game
        options = self.build_options()
        super().__init__(placeholder="🎨 選擇你的隊伍顏色...", min_values=1, max_values=1, options=options, row=0)
        
    def build_options(self) -> List[discord.SelectOption]:
        options = []
        max_players = 1 if self.game.mode == "Solo" else 2
        for team_name, team in self.game.teams.items():
            count = len(team.players)
            options.append(discord.SelectOption(
                label=f"{team_name}隊 ({count}/{max_players} 人)",
                value=team_name,
                emoji=team.emoji
            ))
        return options

    async def callback(self, interaction: discord.Interaction):
        view: LobbyView = self.view
        selected_team_name = self.values[0]
        game = view.cog.active_games.get(view.channel_id)
        
        if not game:
            await interaction.response.send_message("❌ 大廳不存在。", ephemeral=True)
            return
            
        user_id = str(interaction.user.id)
        max_players = 1 if game.mode == "Solo" else 2
        target_team = game.teams[selected_team_name]
        
        if len(target_team.players) >= max_players:
            if any(p.id == user_id for p in target_team.players):
                await interaction.response.send_message(f"⚠️ 你已經在{selected_team_name}了！", ephemeral=True)
            else:
                await interaction.response.send_message(f"❌ {selected_team_name}已滿員！", ephemeral=True)
            return

        existing_player = game.player_map.get(user_id)
        if existing_player:
            existing_player.team.players.remove(existing_player)
            existing_player.team = target_team
            target_team.players.append(existing_player)
            existing_player.location = f"{target_team.name}基地"
        else:
            player = Player(user_id, interaction.user.display_name, target_team, is_bot=False)
            target_team.players.append(player)
            game.players.append(player)
            game.player_map[user_id] = player
            
        # Refresh options
        self.options = self.build_options()
        
        host_id = view.cog.lobby_hosts.get(view.channel_id)
        host = interaction.guild.get_member(host_id) or interaction.user
        embed = view.cog.create_lobby_embed(game, host)
        await interaction.response.edit_message(embed=embed, view=view)


# --- MAIN IN-GAME VIEW ---
class GameMainView(discord.ui.View):
    def __init__(self, cog: BedWarsCog, channel_id: int):
        super().__init__(timeout=None)
        self.cog = cog
        self.channel_id = channel_id

    @discord.ui.button(label="👉 選擇行動 (私人面板)", style=discord.ButtonStyle.blurple)
    async def select_action(self, interaction: discord.Interaction, button: discord.ui.Button):
        game = self.cog.active_games.get(self.channel_id)
        if not game:
            await interaction.response.send_message("❌ 對決不存在。", ephemeral=True)
            return
            
        player = game.player_map.get(str(interaction.user.id))
        if not player:
            await interaction.response.send_message("❌ 你不是這場比賽的玩家！", ephemeral=True)
            return
            
        if not player.is_alive:
            await interaction.response.send_message("💀 你已陣亡，正在等待回合結束後復活！", ephemeral=True)
            return
            
        view = PlayerActionView(game, player, interaction)
        await interaction.response.send_message(
            content=f"### 🛡️ 床戰個人面板 - **{player.name}**\n{player.display_status()}\n📍 目前位置：**{player.location}**",
            view=view,
            ephemeral=True
        )


# --- PLAYER ACTION PANEL (EPHEMERAL) ---
class PlayerActionView(discord.ui.View):
    def __init__(self, game: BedWarsGame, player: Player, parent_interaction: discord.Interaction):
        super().__init__(timeout=60)
        self.game = game
        self.player = player
        self.parent_interaction = parent_interaction
        
        # Row 0: Movement (Dynamic component)
        self.add_item(MoveSelect(game, player))
        
        # Row 1: Attack enemies (Dynamic component)
        enemies = [p for p in game.players if p.is_alive and p.team != player.team and p.location == player.location]
        if enemies:
            self.add_item(AttackSelect(enemies))
            
        # Configure attack bed button status (row 3)
        is_at_enemy_base = "基地" in player.location and player.location != f"{player.team.name}基地"
        if is_at_enemy_base:
            enemy_team = player.location.replace("基地", "")
            if not game.beds_status.get(enemy_team, True):
                self.attack_bed_btn.label = f"💥 攻擊 {enemy_team} 的床"
                self.attack_bed_btn.disabled = False
            else:
                self.attack_bed_btn.label = "💥 床已被摧毀"
                self.attack_bed_btn.disabled = True
        else:
            self.attack_bed_btn.label = "💥 攻擊床 (必須在敵方基地)"
            self.attack_bed_btn.disabled = True

    # --- Shop Category Buttons ---
    @discord.ui.button(label="⚔️ 武器鐵匠", style=discord.ButtonStyle.primary, row=2)
    async def btn_weapons(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.open_shop_category(interaction, "weapons", "⚔️ 武器鐵匠鋪")

    @discord.ui.button(label="🛡️ 防具工具", style=discord.ButtonStyle.primary, row=2)
    async def btn_gear(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.open_shop_category(interaction, "armor_tools", "🛡️ 防具防線與挖掘工具")

    @discord.ui.button(label="🧱 建造床防禦", style=discord.ButtonStyle.primary, row=2)
    async def btn_defenses(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.open_shop_category(interaction, "defenses", "🧱 建造床防禦牆")

    @discord.ui.button(label="🧪 特殊道具", style=discord.ButtonStyle.success, row=2)
    async def btn_utilities(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.open_shop_category(interaction, "utilities", "🧪 特殊功能道具與團隊升級")

    async def open_shop_category(self, interaction: discord.Interaction, category: str, cat_name: str):
        is_at_base = self.player.location == f"{self.player.team.name}基地"
        if not is_at_base:
            await interaction.response.send_message("❌ 你必須在自己的基地才能訪問商店！", ephemeral=True)
            return
            
        view = ShopCategoryView(self.game, self.player, category, self, self.parent_interaction)
        await interaction.response.edit_message(
            content=f"### {cat_name} ─ **{self.player.name}**\n{self.player.display_status()}\n📍 基地位置：**{self.player.location}**",
            view=view
        )

    # --- Active Action Buttons ---
    @discord.ui.button(label="💥 攻擊床", style=discord.ButtonStyle.danger, row=3)
    async def attack_bed_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        enemy_team = self.player.location.replace("基地", "")
        self.player.pending_action = {"type": "attack_bed", "target_team": enemy_team}
        self.player.is_ready = True
        
        for item in self.children:
            item.disabled = True
        await interaction.response.edit_message(content=f"✅ **本回合行動已鎖定**：攻擊 {enemy_team} 的床！", view=self)

    @discord.ui.button(label="📥 收集資源 / 原地防守", style=discord.ButtonStyle.success, row=3)
    async def gather_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.player.pending_action = {"type": "gather"}
        self.player.is_ready = True
        
        for item in self.children:
            item.disabled = True
        await interaction.response.edit_message(content="✅ **本回合行動已鎖定**：原地防守並收集雙倍產量資源！", view=self)


# --- SHOP SUB-CATEGORY PANEL VIEW ---
class ShopCategoryView(discord.ui.View):
    def __init__(self, game: BedWarsGame, player: Player, category: str, main_view: PlayerActionView, parent_interaction: discord.Interaction):
        super().__init__(timeout=60)
        self.game = game
        self.player = player
        self.category = category
        self.main_view = main_view
        self.parent_interaction = parent_interaction
        
        # Add dynamic select dynamically
        self.shop_select = ShopCategorySelect(game, player, category)
        self.add_item(self.shop_select)

    @discord.ui.button(label="🔙 返回個人面板", style=discord.ButtonStyle.secondary, row=1)
    async def back_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Create a fresh new PlayerActionView to avoid manual re-add bugs
        view = PlayerActionView(self.game, self.player, self.parent_interaction)
        await interaction.response.edit_message(
            content=f"### 🛡️ 床戰個人面板 - **{self.player.name}**\n{self.player.display_status()}\n📍 目前位置：**{self.player.location}**",
            view=view
        )

    async def update_category_panel(self, interaction: discord.Interaction, msg: str):
        # Rebuild options of the select
        self.shop_select.options = self.shop_select.build_options()
        
        cat_names = {
            "weapons": "⚔️ 武器鐵匠鋪",
            "armor_tools": "🛡️ 防具防線與挖掘工具",
            "defenses": "🧱 建造床防禦牆",
            "utilities": "🧪 特殊功能道具與團隊升級"
        }
        cat_name = cat_names.get(self.category, "🛒 商店")
        
        await interaction.response.edit_message(
            content=f"### {cat_name} ─ **{self.player.name}**\n{msg}\n\n{self.player.display_status()}\n📍 基地位置：**{self.player.location}**",
            view=self
        )


class ShopCategorySelect(discord.ui.Select):
    def __init__(self, game: BedWarsGame, player: Player, category: str):
        self.game = game
        self.player = player
        self.category = category
        options = self.build_options()
        super().__init__(placeholder="🛒 點此選購商品...", min_values=1, max_values=1, options=options, row=0)
        
    def build_options(self) -> List[discord.SelectOption]:
        options = []
        category = self.category
        if category == "weapons":
            options.append(discord.SelectOption(label="石劍 (10 鐵)", value="石劍", emoji="⚔️", description="基礎攻擊力：5 DMG"))
            options.append(discord.SelectOption(label="鐵劍 (7 金)", value="鐵劍", emoji="⚔️", description="基礎攻擊力：6 DMG"))
            options.append(discord.SelectOption(label="鑽石劍 (4 綠寶石)", value="鑽石劍", emoji="⚔️", description="基礎攻擊力：7 DMG"))
        elif category == "armor_tools":
            options.append(discord.SelectOption(label="鎖子甲 (40 鐵)", value="鎖子甲", emoji="🛡️", description="傷害減免 +10%"))
            options.append(discord.SelectOption(label="鐵防具 (12 金)", value="鐵防具", emoji="🛡️", description="傷害減免 +20%"))
            options.append(discord.SelectOption(label="鑽石防具 (6 綠寶石)", value="鑽石防具", emoji="🛡️", description="傷害減免 +30%"))
            options.append(discord.SelectOption(label="剪刀 (20 鐵)", value="剪刀", emoji="🛠️", description="秒破羊毛床防禦"))
            options.append(discord.SelectOption(label="木斧 (10 鐵)", value="木斧", emoji="🛠️", description="快速砍伐木頭床防禦"))
            options.append(discord.SelectOption(label="鐵鎬 (3 金)", value="鐵鎬", emoji="🛠️", description="快速開採黑曜石床防禦"))
        elif category == "defenses":
            options.append(discord.SelectOption(label="羊毛床防禦 (4 鐵)", value="羊毛防禦", emoji="🧱", description="+15 HP 床防護，極易被剪刀破壞"))
            options.append(discord.SelectOption(label="木頭床防禦 (12 鐵)", value="木頭防禦", emoji="🧱", description="+35 HP 床防護，需要斧頭快速開採"))
            options.append(discord.SelectOption(label="黑曜石床防禦 (4 金)", value="黑曜石防禦", emoji="🧱", description="+80 HP 床防護，極難開採，需鐵鎬"))
        elif category == "utilities":
            options.append(discord.SelectOption(label="金蘋果 (3 金)", value="金蘋果", emoji="🍎", description="立即回復玩家 8 HP"))
            options.append(discord.SelectOption(label="終界珍珠 (4 綠寶石)", value="終界珍珠", emoji="🔮", description="本回合旅行絕對安全，不會掉入虛空"))
            options.append(discord.SelectOption(label="火球 (40 鐵)", value="火球", emoji="☄️", description="往任意節點炸去，造成5傷並削減床防禦HP"))
            options.append(discord.SelectOption(label="團隊鋒利 (4 鑽石)", value="Sharpness", emoji="✨", description="團隊所有人劍刃永久傷害 +1"))
            options.append(discord.SelectOption(label="團隊保護 (2 鑽石)", value="Protection", emoji="🛡️", description="團隊所有人獲得 +10% 保護"))
            options.append(discord.SelectOption(label="團隊資源熔爐 (2 鑽石)", value="Forge", emoji="⚙️", description="基地資源生成速度增加 +50%"))
        return options

    async def callback(self, interaction: discord.Interaction):
        view: ShopCategoryView = self.view
        item_val = self.values[0]
        p = view.player
        
        success = False
        msg = ""
        
        category = None
        for cat in ["weapons", "armor", "tools", "defenses", "utilities"]:
            lookup_val = item_val
            for key in SHOP_ITEMS[cat]:
                if key.startswith(lookup_val) or lookup_val in key:
                    category = cat
                    item_val = key
                    break
            if category:
                break
                
        if category:
            details = SHOP_ITEMS[category][item_val]
            cost_type = details["cost_type"]
            cost = details["cost"]
            emoji = RESOURCE_EMOJIS[cost_type]
            
            if p.resources.get(cost_type, 0) >= cost:
                p.resources[cost_type] -= cost
                success = True
                
                if category == "weapons":
                    p.sword = item_val
                    msg = f"🟢 成功購買了 **{item_val}**！(-{cost}{emoji})"
                elif category == "armor":
                    p.armor = item_val
                    msg = f"🟢 成功購買了 **{item_val}**！(-{cost}{emoji})"
                elif category == "tools":
                    p.tools.add(details["target"])
                    msg = f"🟢 成功購買了工具：**{item_val}**！(-{cost}{emoji})"
                elif category == "defenses":
                    p.team.bed_defense = details["type"]
                    p.team.bed_defense_hp = details["hp"]
                    msg = f"🟢 成功搭建了 **{details['type']}** 床防禦！(-{cost}{emoji})"
                elif category == "utilities":
                    if item_val == "金蘋果":
                        p.hp = min(p.max_hp, p.hp + 8)
                        msg = f"🟢 購買並吃下了金蘋果！恢復了 8 HP。(-{cost}{emoji})"
                    elif item_val == "終界珍珠":
                        if not p.pending_action:
                            p.pending_action = {"type": "shop", "purchases": []}
                        if "purchases" not in p.pending_action:
                            p.pending_action["purchases"] = []
                        p.pending_action["purchases"].append("終界珍珠")
                        msg = f"🟢 成功購買了 **終界珍珠**，可用於安全旅行！(-{cost}{emoji})"
                    elif item_val == "火球":
                        target_choices = [loc for loc in ["紅隊基地", "藍隊基地", "綠隊基地", "黃隊基地", "鑽石島 A", "鑽石島 B", "綠寶石中心島"] if loc != p.location]
                        target_loc = random.choice(target_choices) if target_choices else p.location
                        
                        view.game.battle_logs.append(f"☄️ **{p.name}** 購買了 **火球** 並向 **{target_loc}** 投擲！")
                        target_players = [tgt for tgt in view.game.players if tgt.is_alive and tgt.location == target_loc]
                        for tp in target_players:
                            dmg_taken = max(1, int(5 * (1 - tp.armor_reduction)))
                            tp.hp -= dmg_taken
                            view.game.battle_logs.append(f"  💥 **{tp.name}** 被爆炸波及，受到了 {dmg_taken} 點傷害！(HP: {tp.hp}/{tp.max_hp})")
                            
                        if "基地" in target_loc:
                            target_team_name = target_loc.replace("基地", "")
                            target_team = view.game.teams[target_team_name]
                            if not target_team.bed_broken and target_team.bed_defense_hp > 0:
                                target_team.bed_defense_hp = max(0, target_team.bed_defense_hp - 20)
                                view.game.battle_logs.append(f"  🛏️ **{target_team_name}隊** 的床防禦值降低了 20 HP！(剩餘：{target_team.bed_defense_hp})")
                                if target_team.bed_defense_hp == 0:
                                    target_team.bed_defense = "無"
                                    view.game.battle_logs.append(f"  🔥 **{target_team_name}隊 的床防禦** 被完全摧毀！")
                        msg = f"🟢 向 {target_loc} 投擲了**火球**！(-{cost}{emoji})"
            else:
                msg = f"❌ 資源不足！需要 **{cost}** {emoji}{cost_type}。"
                
        elif item_val in ["Sharpness", "Protection", "Forge"]:
            diamonds = p.resources.get("diamond", 0)
            emoji = RESOURCE_EMOJIS["diamond"]
            
            if item_val == "Sharpness" and diamonds >= 4 and not p.team.sharpness:
                p.resources["diamond"] -= 4
                p.team.sharpness = True
                success = True
                msg = f"🟢 團隊成功升級 **鋒利**！(-4 {emoji})"
            elif item_val == "Protection" and diamonds >= 2 and p.team.protection_level < 4:
                p.resources["diamond"] -= 2
                p.team.protection_level += 1
                success = True
                msg = f"🟢 團隊 **保護** 升級至等級 {p.team.protection_level}！(-2 {emoji})"
            elif item_val == "Forge" and diamonds >= 2 and p.team.forge_level < 3:
                p.resources["diamond"] -= 2
                p.team.forge_level += 1
                success = True
                msg = f"🟢 團隊 **資源熔爐** 升級至等級 {p.team.forge_level}！(-2 {emoji})"
            else:
                if item_val == "Sharpness" and p.team.sharpness:
                    msg = "❌ 鋒利升級已處於啟用狀態！"
                elif item_val == "Protection" and p.team.protection_level >= 4:
                    msg = "❌ 保護升級已達最高上限！"
                elif item_val == "Forge" and p.team.forge_level >= 3:
                    msg = "❌ 資源熔爐已達最高上限！"
                else:
                    cost = 4 if item_val == "Sharpness" else 2
                    msg = f"❌ 資源不足！需要 **{cost}** {emoji} 鑽石。"

        await view.update_category_panel(interaction, msg)


# --- MOVE SELECT DROPDOWN ---
class MoveSelect(discord.ui.Select):
    def __init__(self, game: BedWarsGame, player: Player):
        options = []
        locations = [
            "紅隊基地", "藍隊基地", "綠隊基地", "黃隊基地",
            "鑽石島 A", "鑽石島 B", "綠寶石中心島"
        ]
        for loc in locations:
            if loc != player.location:
                emoji = "🏠" if "基地" in loc else ("💎" if "鑽石" in loc else "🟢")
                options.append(discord.SelectOption(label=loc, value=loc, emoji=emoji))
                
        super().__init__(placeholder="🏃 選擇移動目的地...", min_values=1, max_values=1, options=options, row=0)

    async def callback(self, interaction: discord.Interaction):
        view: PlayerActionView = self.view
        dest = self.values[0]
        view.player.pending_action = {"type": "move", "target": dest}
        view.player.is_ready = True
        
        for item in view.children:
            item.disabled = True
        await interaction.response.edit_message(content=f"✅ **本回合行動已鎖定**：移動至 **{dest}**！", view=view)


# --- ATTACK SELECT DROPDOWN ---
class AttackSelect(discord.ui.Select):
    def __init__(self, enemies: List[Player]):
        options = []
        for e in enemies:
            options.append(discord.SelectOption(label=f"{e.name} (HP: {e.hp})", value=e.id, emoji=e.team.emoji))
            
        super().__init__(placeholder="⚔️ 選擇同位置的敵人進行攻擊...", min_values=1, max_values=1, options=options, row=1)

    async def callback(self, interaction: discord.Interaction):
        view: PlayerActionView = self.view
        target_id = self.values[0]
        target = view.game.player_map.get(target_id)
        
        view.player.pending_action = {"type": "attack_player", "target_id": target_id}
        view.player.is_ready = True
        
        for item in view.children:
            item.disabled = True
        await interaction.response.edit_message(content=f"✅ **本回合行動已鎖定**：攻擊玩家 **{target.name}**！", view=view)
