import os
import discord
from discord.ext import commands
from dotenv import load_dotenv
import asyncio

# Load environment variables
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

# Setup Intents
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

# Initialize Bot
bot = commands.Bot(command_prefix=["!", "."], intents=intents)

@bot.event
async def on_ready():
    print(f"✅ Bot is online! Logged in as: {bot.user} (ID: {bot.user.id})")
    
    # Synchronize slash commands
    try:
        print("🔄 Syncing slash commands...")
        synced = await bot.tree.sync()
        print(f"✔ Successfully synced {len(synced)} slash commands!")
    except Exception as e:
        print(f"❌ Failed to sync slash commands: {e}")

async def load_extensions():
    # Import and add the BedWars Cog directly
    from cogs.bedwars_cog import BedWarsCog
    await bot.add_cog(BedWarsCog(bot))
    print("✔ Loaded BedWars Cog successfully!")

async def main():
    async with bot:
        await load_extensions()
        if not TOKEN or TOKEN == "YOUR_DISCORD_BOT_TOKEN_HERE":
            print("⚠ DISCORD_TOKEN is missing or set to the default placeholder in .env!")
            print("Please create/configure your Discord Bot application on the developer portal,")
            print("copy your bot token, paste it into the .env file, and restart the bot.")
        else:
            await bot.start(TOKEN)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("🔌 Bot shut down successfully.")
