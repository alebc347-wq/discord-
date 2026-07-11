import discord
from typing import Dict, List, Set, Optional, Any

# Emojis for resource representation
RESOURCE_EMOJIS = {
    "iron": "🪙",
    "gold": "💛",
    "diamond": "💎",
    "emerald": "🟢"
}

# Base items available in the shop
SHOP_ITEMS = {
    "weapons": {
        "石劍": {"cost_type": "iron", "cost": 10, "dmg": 5},
        "鐵劍": {"cost_type": "gold", "cost": 7, "dmg": 6},
        "鑽石劍": {"cost_type": "emerald", "cost": 4, "dmg": 7}
    },
    "armor": {
        "鎖子甲": {"cost_type": "iron", "cost": 40, "reduction": 0.10},
        "鐵防具": {"cost_type": "gold", "cost": 12, "reduction": 0.20},
        "鑽石防具": {"cost_type": "emerald", "cost": 6, "reduction": 0.30}
    },
    "tools": {
        "剪刀": {"cost_type": "iron", "cost": 20, "target": "羊毛"},
        "木斧": {"cost_type": "iron", "cost": 10, "target": "木頭"},
        "鐵鎬": {"cost_type": "gold", "cost": 3, "target": "黑曜石"}
    },
    "defenses": {
        "羊毛防禦": {"cost_type": "iron", "cost": 4, "type": "羊毛", "hp": 15},
        "木頭防禦": {"cost_type": "iron", "cost": 12, "type": "木頭", "hp": 35},
        "黑曜石防禦": {"cost_type": "gold", "cost": 4, "type": "黑曜石", "hp": 80}
    },
    "utilities": {
        "金蘋果": {"cost_type": "gold", "cost": 3, "heal": 8},
        "終界珍珠": {"cost_type": "emerald", "cost": 4},
        "火球": {"cost_type": "iron", "cost": 40, "dmg": 5}
    }
}

class Team:
    def __init__(self, name: str, emoji: str, color_code: int):
        self.name: str = name
        self.emoji: str = emoji
        self.color_code: int = color_code
        self.bed_broken: bool = False
        self.bed_defense: str = "無"
        self.bed_defense_hp: int = 0
        self.sharpness: bool = False
        self.protection_level: int = 0
        self.forge_level: int = 0
        self.players: List['Player'] = []
        self.resources: Dict[str, int] = {"iron": 0, "gold": 0, "diamond": 0, "emerald": 0}

    @property
    def generator_rates(self) -> Dict[str, float]:
        # base rates per turn: 4 iron, 0.5 gold (1 gold every 2 turns)
        rates = {"iron": 4.0, "gold": 0.5, "diamond": 0.0, "emerald": 0.0}
        if self.forge_level == 1:
            rates["iron"] = 6.0
            rates["gold"] = 1.0
        elif self.forge_level == 2:
            rates["iron"] = 8.0
            rates["gold"] = 1.5
        elif self.forge_level == 3:
            rates["iron"] = 8.0
            rates["gold"] = 2.0
            rates["emerald"] = 0.25 # 1 emerald every 4 turns
        return rates

    @property
    def protection_reduction(self) -> float:
        # 10% reduction per level
        return self.protection_level * 0.10

class Player:
    def __init__(self, id: str, name: str, team: Team, is_bot: bool = False):
        self.id: str = id
        self.name: str = name
        self.team: Team = team
        self.is_bot: bool = is_bot
        
        self.hp: int = 20
        self.max_hp: int = 20
        self.sword: str = "木劍"
        self.armor: str = "皮革防具"
        self.tools: Set[str] = set()
        self.resources: Dict[str, int] = {"iron": 0, "gold": 0, "diamond": 0, "emerald": 0}
        self.location: str = f"{team.name}基地"
        self.is_alive: bool = True
        
        # Action tracking
        self.pending_action: Optional[Dict[str, Any]] = None
        self.is_ready: bool = False
        
        # Stats
        self.kills: int = 0
        self.deaths: int = 0
        self.bed_breaks: int = 0

    @property
    def sword_damage(self) -> int:
        dmg = 4  # 木劍基礎傷害
        if self.sword == "石劍":
            dmg = 5
        elif self.sword == "鐵劍":
            dmg = 6
        elif self.sword == "鑽石劍":
            dmg = 7
            
        if self.team.sharpness:
            dmg += 1
        return dmg

    @property
    def armor_reduction(self) -> float:
        reduction = 0.0
        if self.armor == "鎖子甲":
            reduction = 0.10
        elif self.armor == "鐵防具":
            reduction = 0.20
        elif self.armor == "鑽石防具":
            reduction = 0.30
            
        # Add team protection
        reduction += self.team.protection_reduction
        return min(reduction, 0.70)  # Cap reduction at 70% to prevent invincibility

    def reset_inventory(self):
        """Called on death. Keep armor, but lose resources, tools, and revert to Wooden Sword."""
        self.hp = self.max_hp
        self.sword = "木劍"
        self.tools = set()
        self.resources = {"iron": 0, "gold": 0, "diamond": 0, "emerald": 0}
        self.location = f"{self.team.name}基地"
        self.is_alive = True
        self.pending_action = None
        self.is_ready = False

    def add_resources(self, resource: str, amount: int):
        if resource in self.resources:
            self.resources[resource] += amount

    def remove_resources(self, resource: str, amount: int) -> bool:
        if resource in self.resources and self.resources[resource] >= amount:
            self.resources[resource] -= amount
            return True
        return False

    def display_status(self) -> str:
        res_str = " ".join([f"{RESOURCE_EMOJIS[r]}{self.resources[r]}" for r in ["iron", "gold", "diamond", "emerald"]])
        tools_str = ", ".join(self.tools) if self.tools else "無"
        return (
            f"❤️ HP: {self.hp}/{self.max_hp} | ⚔️ {self.sword} | 🛡️ {self.armor}\n"
            f"🛠️ 工具: {tools_str}\n"
            f"🎒 資源: {res_str}"
        )
