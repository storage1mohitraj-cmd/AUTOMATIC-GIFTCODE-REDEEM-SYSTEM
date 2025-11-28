import discord
from discord.ext import commands
from discord import app_commands
from db.mongo_adapter import mongo
import pymongo
import asyncio
import time
from typing import List
from datetime import datetime
import os
from .login_handler import LoginHandler

class PaginationView(discord.ui.View):
    def __init__(self, chunks: List[discord.Embed], author_id: int):
        super().__init__(timeout=7200)
        self.chunks = chunks
        self.current_page = 0
        self.message = None
        self.author_id = author_id
        self.update_buttons()

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message("You cannot use these buttons.", ephemeral=True)
            return False
        return True

    @discord.ui.button(emoji="⬅️", style=discord.ButtonStyle.blurple, disabled=True)
    async def previous_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._handle_page_change(interaction, -1)

    @discord.ui.button(emoji="➡️", style=discord.ButtonStyle.blurple)
    async def next_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._handle_page_change(interaction, 1)

    async def _handle_page_change(self, interaction: discord.Interaction, change: int):
        self.current_page = max(0, min(self.current_page + change, len(self.chunks) - 1))
        self.update_buttons()
        await self.update_page(interaction)

    def update_buttons(self):
        self.previous_page.disabled = self.current_page == 0
        self.next_page.disabled = self.current_page == len(self.chunks) - 1

    async def update_page(self, interaction: discord.Interaction):
        embed = self.chunks[self.current_page]
        embed.set_footer(text=f"Page {self.current_page + 1}/{len(self.chunks)}")
        await interaction.response.edit_message(embed=embed, view=self)

    async def on_timeout(self) -> None:
        for item in self.children:
            if isinstance(item, discord.ui.Button):
                item.disabled = True
        if self.message:
            try:
                await self.message.edit(view=self)
            except discord.HTTPException:
                pass

def fix_rtl(text):
    return f"\u202B{text}\u202C"

class AllianceMemberOperations(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        
        self.level_mapping = {
            31: "30-1", 32: "30-2", 33: "30-3", 34: "30-4",
            35: "FC 1", 36: "FC 1 - 1", 37: "FC 1 - 2", 38: "FC 1 - 3", 39: "FC 1 - 4",
            40: "FC 2", 41: "FC 2 - 1", 42: "FC 2 - 2", 43: "FC 2 - 3", 44: "FC 2 - 4",
            45: "FC 3", 46: "FC 3 - 1", 47: "FC 3 - 2", 48: "FC 3 - 3", 49: "FC 3 - 4",
            50: "FC 4", 51: "FC 4 - 1", 52: "FC 4 - 2", 53: "FC 4 - 3", 54: "FC 4 - 4",
            55: "FC 5", 56: "FC 5 - 1", 57: "FC 5 - 2", 58: "FC 5 - 3", 59: "FC 5 - 4",
            60: "FC 6", 61: "FC 6 - 1", 62: "FC 6 - 2", 63: "FC 6 - 3", 64: "FC 6 - 4",
            65: "FC 7", 66: "FC 7 - 1", 67: "FC 7 - 2", 68: "FC 7 - 3", 69: "FC 7 - 4",
            70: "FC 8", 71: "FC 8 - 1", 72: "FC 8 - 2", 73: "FC 8 - 3", 74: "FC 8 - 4",
            75: "FC 9", 76: "FC 9 - 1", 77: "FC 9 - 2", 78: "FC 9 - 3", 79: "FC 9 - 4",
            80: "FC 10", 81: "FC 10 - 1", 82: "FC 10 - 2", 83: "FC 10 - 3", 84: "FC 10 - 4"
        }

        self.fl_emojis = {
            range(35, 40): "<:fc1:1326751863764156528>",
            range(40, 45): "<:fc2:1326751886954594315>",
            range(45, 50): "<:fc3:1326751903912034375>",
            range(50, 55): "<:fc4:1326751938674692106>",
            range(55, 60): "<:fc5:1326751952750776331>",
            range(60, 65): "<:fc6:1326751966184869981>",
            range(65, 70): "<:fc7:1326751983939489812>",
            range(70, 75): "<:fc8:1326751996707082240>",
            range(75, 80): "<:fc9:1326752008505528331>",
            range(80, 85): "<:fc10:1326752023001174066>"
        }

        self.log_directory = 'log'
        if not os.path.exists(self.log_directory):
            os.makedirs(self.log_directory)
        self.log_file = os.path.join(self.log_directory, 'alliance_memberlog.txt')
        
        # Initialize login handler for centralized API management
        self.login_handler = LoginHandler()

    def log_message(self, message: str):
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        log_entry = f"[{timestamp}] {message}\n"
        
        with open(self.log_file, 'a', encoding='utf-8') as f:
            f.write(log_entry)

    def get_fl_emoji(self, fl_level: int) -> str:
        for level_range, emoji in self.fl_emojis.items():
            if fl_level in level_range:
                return emoji
        return "🔥"

    async def handle_member_operations(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="👥 Alliance Member Operations",
            description=(
                "Please select an operation from below:\n\n"
                "**Available Operations:**\n"
                "➕ `Add Member` - Add new members to alliance\n"
                "➖ `Remove Member` - Remove members from alliance\n"
                "📋 `View Members` - View alliance member list\n"
                "🔄 `Transfer Member` - Transfer members to another alliance\n"
                "🏠 `Main Menu` - Return to main menu"
            ),
            color=discord.Color.blue()
        )
        
        embed.set_footer(text="Select an option to continue")

        class MemberOperationsView(discord.ui.View):
            def __init__(self, cog):
                super().__init__()
                self.cog = cog
                self.bot = cog.bot

            @discord.ui.button(
                label="Add Member",
                emoji="➕",
                style=discord.ButtonStyle.success,
                custom_id="add_member",
                row=0
            )
            async def add_member_button(self, button_interaction: discord.Interaction, button: discord.ui.Button):
                try:
                    admin = mongo.admin.find_one({"id": button_interaction.user.id})
                    
                    if not admin:
                        await button_interaction.response.send_message(
                            "❌ You do not have permission to use this command.", 
                            ephemeral=True
                        )
                        return
                        
                    is_initial = admin.get("is_initial", 0)

                    alliances, special_alliances, is_global = await self.cog.get_admin_alliances(
                        button_interaction.user.id, 
                        button_interaction.guild_id
                    )
                    
                    if not alliances:
                        await button_interaction.response.send_message(
                            "❌ No alliances found for your permissions.", 
                            ephemeral=True
                        )
                        return

                    special_alliance_text = ""
                    if special_alliances:
                        special_alliance_text = "\n\n**Special Access Alliances**\n"
                        special_alliance_text += "━━━━━━━━━━━━━━━━━━━━━━\n"
                        for _, name in special_alliances:
                            special_alliance_text += f"🔸 {name}\n"
                        special_alliance_text += "━━━━━━━━━━━━━━━━━━━━━━"

                    select_embed = discord.Embed(
                        title="📋 Alliance Selection",
                        description=(
                            "Please select an alliance to add members:\n\n"
                            "**Permission Details**\n"
                            "━━━━━━━━━━━━━━━━━━━━━━\n"
                            f"👤 **Access Level:** `{'Global Admin' if is_initial == 1 else 'Server Admin'}`\n"
                            f"🔍 **Access Type:** `{'All Alliances' if is_initial == 1 else 'Server + Special Access'}`\n"
                            f"📊 **Available Alliances:** `{len(alliances)}`\n"
                            "━━━━━━━━━━━━━━━━━━━━━━"
                            f"{special_alliance_text}"
                        ),
                        color=discord.Color.green()
                    )

                    alliances_with_counts = []
                    for alliance_id, name in alliances:
                        member_count = mongo.users.count_documents({"alliance": int(alliance_id)})
                        alliances_with_counts.append((alliance_id, name, member_count))

                    view = AllianceSelectView(alliances_with_counts, self.cog)
                    
                    async def select_callback(interaction: discord.Interaction):
                        alliance_id = int(view.current_select.values[0])
                        await interaction.response.send_modal(AddMemberModal(alliance_id))

                    view.callback = select_callback
                    await button_interaction.response.send_message(
                        embed=select_embed,
                        view=view,
                        ephemeral=True
                    )

                except Exception as e:
                    self.log_message(f"Error in add_member_button: {e}")
                    await button_interaction.response.send_message(
                        "An error occurred while processing your request.", 
                        ephemeral=True
                    )

            @discord.ui.button(
                label="Remove Member",
                emoji="➖",
                style=discord.ButtonStyle.danger,
                custom_id="remove_member",
                row=0
            )
            async def remove_member_button(self, button_interaction: discord.Interaction, button: discord.ui.Button):
                try:
                    with sqlite3.connect('db/settings.sqlite') as settings_db:
                        cursor = settings_db.cursor()
                        cursor.execute("SELECT is_initial FROM admin WHERE id = ?", (button_interaction.user.id,))
                        admin_result = cursor.fetchone()
                        
                        if not admin_result:
                            await button_interaction.response.send_message(
                                "❌ You are not authorized to use this command.", 
                                ephemeral=True
                            )
                            return
                            
                        is_initial = admin_result[0]

                    alliances, special_alliances, is_global = await self.cog.get_admin_alliances(
                        button_interaction.user.id, 
                        button_interaction.guild_id
                    )
                    
                    if not alliances:
                        await button_interaction.response.send_message(
                            "❌ Your authorized alliance was not found.", 
                            ephemeral=True
                        )
                        return

                    special_alliance_text = ""
                    if special_alliances:
                        special_alliance_text = "\n\n**Special Access Alliances**\n"
                        special_alliance_text += "━━━━━━━━━━━━━━━━━━━━━━\n"
                        for _, name in special_alliances:
                            special_alliance_text += f"🔸 {name}\n"
                        special_alliance_text += "━━━━━━━━━━━━━━━━━━━━━━"

                    select_embed = discord.Embed(
                        title="🗑️ Alliance Selection - Member Deletion",
                        description=(
                            "Please select an alliance to remove members:\n\n"
                            "**Permission Details**\n"
                            "━━━━━━━━━━━━━━━━━━━━━━\n"
                            f"👤 **Access Level:** `{'Global Admin' if is_initial == 1 else 'Server Admin'}`\n"
                            f"🔍 **Access Type:** `{'All Alliances' if is_initial == 1 else 'Server + Special Access'}`\n"
                            f"📊 **Available Alliances:** `{len(alliances)}`\n"
                            "━━━━━━━━━━━━━━━━━━━━━━"
                            f"{special_alliance_text}"
                        ),
                        color=discord.Color.red()
                    )

                    alliances_with_counts = []
                    for alliance_id, name in alliances:
                        with sqlite3.connect('db/users.sqlite') as users_db:
                            cursor = users_db.cursor()
                            cursor.execute("SELECT COUNT(*) FROM users WHERE alliance = ?", (alliance_id,))
                            member_count = cursor.fetchone()[0]
                            alliances_with_counts.append((alliance_id, name, member_count))

                    view = AllianceSelectView(alliances_with_counts, self.cog)
                    
                    async def select_callback(interaction: discord.Interaction):
                        alliance_id = int(view.current_select.values[0])
                        
                        alliance_doc = mongo.alliance_list.find_one({"alliance_id": int(alliance_id)})
                        alliance_name = alliance_doc["name"] if alliance_doc else "Unknown"
                        
                        members = list(mongo.users.find(
                            {"alliance": int(alliance_id)},
                            {"fid": 1, "nickname": 1, "furnace_lv": 1}
                        ).sort([("furnace_lv", -1), ("nickname", 1)]))
                        
                        # Convert to list of tuples to match previous format
                        members = [(m["fid"], m["nickname"], m["furnace_lv"]) for m in members]
                            
                        if not members:
                            await interaction.response.send_message(
                                "❌ No members found in this alliance.", 
                                ephemeral=True
                            )
                            return

                        max_fl = max(member[2] for member in members)
                        avg_fl = sum(member[2] for member in members) / len(members)

                        member_embed = discord.Embed(
                            title=f"👥 {alliance_name} -  Member Selection",
                            description=(
                                "```ml\n"
                                "Alliance Statistics\n"
                                "══════════════════════════\n"
                                f"📊 Total Member     : {len(members)}\n"
                                f"⚔️ Highest Level    : {self.cog.level_mapping.get(max_fl, str(max_fl))}\n"
                                f"📈 Average Level    : {self.cog.level_mapping.get(int(avg_fl), str(int(avg_fl)))}\n"
                                "══════════════════════════\n"
                                "```\n"
                                "Select the member you want to delete:"
                            ),
                            color=discord.Color.red()
                        )

                        member_view = MemberSelectView(members, alliance_name, self.cog, is_remove_operation=True)
                        
                        async def member_callback(member_interaction: discord.Interaction):
                            selected_value = member_view.current_select.values[0]
                            
                            if selected_value == "all":
                                confirm_embed = discord.Embed(
                                    title="⚠️ Confirmation Required",
                                    description=f"A total of **{len(members)}** members will be deleted.\nDo you confirm?",
                                    color=discord.Color.red()
                                )
                                
                                confirm_view = discord.ui.View()
                                confirm_button = discord.ui.Button(
                                    label="✅ Confirm", 
                                    style=discord.ButtonStyle.danger, 
                                    custom_id="confirm_all"
                                )
                                cancel_button = discord.ui.Button(
                                    label="❌ Cancel", 
                                    style=discord.ButtonStyle.secondary, 
                                    custom_id="cancel_all"
                                )
                                
                                confirm_view.add_item(confirm_button)
                                confirm_view.add_item(cancel_button)

                                async def confirm_callback(confirm_interaction: discord.Interaction):
                                    if confirm_interaction.data["custom_id"] == "confirm_all":
                                        removed_members = list(mongo.users.find({"alliance": int(alliance_id)}, {"fid": 1, "nickname": 1}))
                                        removed_members = [(m["fid"], m["nickname"]) for m in removed_members]
                                        
                                        mongo.users.delete_many({"alliance": int(alliance_id)})
                                        
                                        try:
                                            alliance_log_result = mongo.alliance_logs.find_one({"alliance_id": int(alliance_id)})
                                            
                                            if alliance_log_result and alliance_log_result.get("channel_id"):
                                                    log_embed = discord.Embed(
                                                        title="🗑️ Mass Member Removal",
                                                        description=(
                                                            f"**Alliance:** {alliance_name}\n"
                                                            f"**Administrator:** {confirm_interaction.user.name} (`{confirm_interaction.user.id}`)\n"
                                                            f"**Date:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
                                                            f"**Total Members Removed:** {len(removed_members)}\n\n"
                                                            "**Removed Members:**\n"
                                                            "```\n" + 
                                                            "\n".join([f"FID{idx+1}: {fid}" for idx, (fid, _) in enumerate(removed_members[:20])]) +
                                                            (f"\n... ve {len(removed_members) - 20} FID more" if len(removed_members) > 20 else "") +
                                                            "\n```"
                                                        ),
                                                        color=discord.Color.red()
                                                    )
                                                    
                                                    try:
                                                        alliance_channel_id = int(alliance_log_result["channel_id"])
                                                        alliance_log_channel = self.bot.get_channel(alliance_channel_id)
                                                        if alliance_log_channel:
                                                            await alliance_log_channel.send(embed=log_embed)
                                                    except Exception as e:
                                                        self.log_message(f"Alliance Log Sending Error: {e}")
                                        except Exception as e:
                                            self.log_message(f"Log record error: {e}")
                                        
                                        success_embed = discord.Embed(
                                            title="✅ Members Deleted",
                                            description=f"A total of **{len(removed_members)}** members have been successfully deleted.",
                                            color=discord.Color.green()
                                        )
                                        await confirm_interaction.response.edit_message(embed=success_embed, view=None)
                                    else:
                                        cancel_embed = discord.Embed(
                                            title="❌ Operation Cancelled",
                                            description="Member deletion operation has been cancelled.",
                                            color=discord.Color.orange()
                                        )
                                        await confirm_interaction.response.edit_message(embed=cancel_embed, view=None)

                                confirm_button.callback = confirm_callback
                                cancel_button.callback = confirm_callback
                                
                                await member_interaction.response.edit_message(
                                    embed=confirm_embed,
                                    view=confirm_view
                                )
                            
                            else:
                                try:
                                    selected_fid = int(selected_value)
                                    user_doc = mongo.users.find_one({"fid": selected_fid})
                                    nickname = user_doc["nickname"] if user_doc else "Unknown"
                                    
                                    mongo.users.delete_one({"fid": selected_fid})
                                    
                                    try:
                                        alliance_log_result = mongo.alliance_logs.find_one({"alliance_id": int(alliance_id)})
                                        
                                        if alliance_log_result and alliance_log_result.get("channel_id"):
                                                log_embed = discord.Embed(
                                                    title="🗑️ Member Removed",
                                                    description=(
                                                        f"**Alliance:** {alliance_name}\n"
                                                        f"**Administrator:** {member_interaction.user.name} (`{member_interaction.user.id}`)\n"
                                                        f"**Date:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
                                                        f"**Removed Member:**\n"
                                                        f"👤 **Name:** {nickname}\n"
                                                        f"🆔 **FID:** {selected_fid}"
                                                    ),
                                                    color=discord.Color.red()
                                                )
                                                
                                                try:
                                                    alliance_channel_id = int(alliance_log_result["channel_id"])
                                                    alliance_log_channel = self.bot.get_channel(alliance_channel_id)
                                                    if alliance_log_channel:
                                                        await alliance_log_channel.send(embed=log_embed)
                                                except Exception as e:
                                                    self.log_message(f"Alliance Log Sending Error: {e}")
                                    except Exception as e:
                                        self.log_message(f"Log record error: {e}")
                                    
                                    success_embed = discord.Embed(
                                        title="✅ Member Deleted",
                                        description=f"**{nickname}** has been successfully deleted.",
                                        color=discord.Color.green()
                                    )
                                    await member_interaction.response.edit_message(embed=success_embed, view=None)
                                    
                                except Exception as e:
                                    self.log_message(f"Error in member removal: {e}")
                                    await member_interaction.response.send_message(
                                        "❌ An error occurred during member removal.",
                                        ephemeral=True
                                    )

                        member_view.callback = member_callback
                        await interaction.response.edit_message(
                            embed=member_embed,
                            view=member_view
                        )

                    view.callback = select_callback
                    await button_interaction.response.send_message(
                        embed=select_embed,
                        view=view,
                        ephemeral=True
                    )

                except Exception as e:
                    self.log_message(f"Error in remove_member_button: {e}")
                    await button_interaction.response.send_message(
                        "❌ An error occurred during the member deletion process.",
                        ephemeral=True
                    )

            @discord.ui.button(
                label="View Members",
                emoji="👥",
                style=discord.ButtonStyle.primary,
                custom_id="view_members",
                row=0
            )
            async def view_members_button(self, button_interaction: discord.Interaction, button: discord.ui.Button):
                try:
                    admin = mongo.admin.find_one({"id": button_interaction.user.id})
                    
                    if not admin:
                        await button_interaction.response.send_message(
                            "❌ You do not have permission to use this command.", 
                            ephemeral=True
                        )
                        return
                        
                    is_initial = admin.get("is_initial", 0)

                    alliances, special_alliances, is_global = await self.cog.get_admin_alliances(
                        button_interaction.user.id, 
                        button_interaction.guild_id
                    )
                    
                    if not alliances:
                        await button_interaction.response.send_message(
                            "❌ No alliance found that you have permission for.", 
                            ephemeral=True
                        )
                        return

                    special_alliance_text = ""
                    if special_alliances:
                        special_alliance_text = "\n\n**Special Access Alliances**\n"
                        special_alliance_text += "━━━━━━━━━━━━━━━━━━━━━━\n"
                        for _, name in special_alliances:
                            special_alliance_text += f"🔸 {name}\n"
                        special_alliance_text += "━━━━━━━━━━━━━━━━━━━━━━"

                    select_embed = discord.Embed(
                        title="👥 Alliance Selection",
                        description=(
                            "Please select an alliance to view members:\n\n"
                            "**Permission Details**\n"
                            "━━━━━━━━━━━━━━━━━━━━━━\n"
                            f"👤 **Access Level:** `{'Global Admin' if is_initial == 1 else 'Server Admin'}`\n"
                            f"🔍 **Access Type:** `{'All Alliances' if is_initial == 1 else 'Server + Special Access'}`\n"
                            f"📊 **Available Alliances:** `{len(alliances)}`\n"
                            "━━━━━━━━━━━━━━━━━━━━━━"
                            f"{special_alliance_text}"
                        ),
                        color=discord.Color.blue()
                    )

                    alliances_with_counts = []
                    for alliance_id, name in alliances:
                        member_count = mongo.users.count_documents({"alliance": int(alliance_id)})
                        alliances_with_counts.append((alliance_id, name, member_count))

                    view = AllianceSelectView(alliances_with_counts, self.cog)
                    
                    async def select_callback(interaction: discord.Interaction):
                        alliance_id = int(view.current_select.values[0])
                        
                        alliance_doc = mongo.alliance_list.find_one({"alliance_id": int(alliance_id)})
                        alliance_name = alliance_doc["name"] if alliance_doc else "Unknown"
                        
                        members = list(mongo.users.find(
                            {"alliance": int(alliance_id)},
                            {"fid": 1, "nickname": 1, "furnace_lv": 1}
                        ).sort([("furnace_lv", -1), ("nickname", 1)]))
                        
                        # Convert to list of tuples to match previous format
                        members = [(m["fid"], m["nickname"], m["furnace_lv"]) for m in members]
                        
                        if not members:
                            await interaction.response.send_message(
                                "❌ No members found in this alliance.", 
                                ephemeral=True
                            )
                            return

                        max_fl = max(member[2] for member in members)
                        avg_fl = sum(member[2] for member in members) / len(members)

                        public_embed = discord.Embed(
                            title=f"👥 {alliance_name} - Member List",
                            description=(
                                "```ml\n"
                                "Alliance Statistics\n"
                                "══════════════════════════\n"
                                f"📊 Total Members    : {len(members)}\n"
                                f"⚔️ Highest Level    : {self.cog.level_mapping.get(max_fl, str(max_fl))}\n"
                                f"📈 Average Level    : {self.cog.level_mapping.get(int(avg_fl), str(int(avg_fl)))}\n"
                                "══════════════════════════\n"
                                "```\n"
                                "**Member List**\n"
                                "━━━━━━━━━━━━━━━━━━━━━━\n"
                            ),
                            color=discord.Color.blue()
                        )

                        members_per_page = 15
                        member_chunks = [members[i:i + members_per_page] for i in range(0, len(members), members_per_page)]
                        embeds = []

                        for page, chunk in enumerate(member_chunks):
                            embed = public_embed.copy()
                            
                            member_list = ""
                            for idx, (fid, nickname, furnace_lv) in enumerate(chunk, start=page * members_per_page + 1):
                                level = self.cog.level_mapping.get(furnace_lv, str(furnace_lv))
                                member_list += f"**{idx:02d}.** 👤 {nickname}\n└ ⚔️ `FC: {level}`\n\n"

                            embed.description += member_list
                            
                            if len(member_chunks) > 1:
                                embed.set_footer(text=f"Page {page + 1}/{len(member_chunks)}")
                            
                            embeds.append(embed)

                        pagination_view = PaginationView(embeds, interaction.user.id)
                        
                        await interaction.response.edit_message(
                            content="✅ Member list has been generated and posted below.",
                            embed=None,
                            view=None
                        )
                        
                        message = await interaction.channel.send(
                            embed=embeds[0],
                            view=pagination_view if len(embeds) > 1 else None
                        )
                        
                        if pagination_view:
                            pagination_view.message = message

                    view.callback = select_callback
                    await button_interaction.response.send_message(
                        embed=select_embed,
                        view=view,
                        ephemeral=True
                    )

                except Exception as e:
                    self.log_message(f"Error in view_members_button: {e}")
                    if not button_interaction.response.is_done():
                        await button_interaction.response.send_message(
                            "❌ An error occurred while displaying the member list.",
                            ephemeral=True
                        )

            @discord.ui.button(
                label="Main Menu", 
                emoji="🏠", 
                style=discord.ButtonStyle.secondary,
                row=2
            )
            async def main_menu_button(self, interaction: discord.Interaction, button: discord.ui.Button):
                await self.cog.show_main_menu(interaction)

            @discord.ui.button(label="Transfer Member", emoji="🔄", style=discord.ButtonStyle.primary)
            async def transfer_member_button(self, button_interaction: discord.Interaction, button: discord.ui.Button):
                try:
                    with sqlite3.connect('db/settings.sqlite') as settings_db:
                        cursor = settings_db.cursor()
                        cursor.execute("SELECT is_initial FROM admin WHERE id = ?", (button_interaction.user.id,))
                        admin_result = cursor.fetchone()
                        
                        if not admin_result:
                            await button_interaction.response.send_message(
                                "❌ You do not have permission to use this command.", 
                                ephemeral=True
                            )
                            return
                            
                        is_initial = admin_result[0]

                    alliances, special_alliances, is_global = await self.cog.get_admin_alliances(
                        button_interaction.user.id, 
                        button_interaction.guild_id
                    )
                    
                    if not alliances:
                        await button_interaction.response.send_message(
                            "❌ No alliance found with your permissions.", 
                            ephemeral=True
                        )
                        return

                    special_alliance_text = ""
                    if special_alliances:
                        special_alliance_text = "\n\n**Special Access Alliances**\n"
                        special_alliance_text += "━━━━━━━━━━━━━━━━━━━━━━\n"
                        for _, name in special_alliances:
                            special_alliance_text += f"🔸 {name}\n"
                        special_alliance_text += "━━━━━━━━━━━━━━━━━━━━━━"

                    select_embed = discord.Embed(
                        title="🔄 Alliance Selection - Member Transfer",
                        description=(
                            "Select the **source** alliance from which you want to transfer members:\n\n"
                            "**Permission Details**\n"
                            "━━━━━━━━━━━━━━━━━━━━━━\n"
                            f"👤 **Access Level:** `{'Global Admin' if is_initial == 1 else 'Server Admin'}`\n"
                            f"🔍 **Access Type:** `{'All Alliances' if is_initial == 1 else 'Server + Special Access'}`\n"
                            f"📊 **Available Alliances:** `{len(alliances)}`\n"
                            "━━━━━━━━━━━━━━━━━━━━━━"
                            f"{special_alliance_text}"
                        ),
                        color=discord.Color.blue()
                    )

                    alliances_with_counts = []
                    for alliance_id, name in alliances:
                        member_count = mongo.users.count_documents({"alliance": int(alliance_id)})
                        alliances_with_counts.append((alliance_id, name, member_count))

                    view = AllianceSelectView(alliances_with_counts, self.cog)
                    
                    async def source_callback(interaction: discord.Interaction):
                        try:
                            source_alliance_id = int(view.current_select.values[0])
                            
                            alliance_doc = mongo.alliance_list.find_one({"alliance_id": int(source_alliance_id)})
                            source_alliance_name = alliance_doc["name"] if alliance_doc else "Unknown"
                            
                            members = list(mongo.users.find(
                                {"alliance": int(source_alliance_id)},
                                {"fid": 1, "nickname": 1, "furnace_lv": 1}
                            ).sort([("furnace_lv", -1), ("nickname", 1)]))
                            
                            members = [(m["fid"], m["nickname"], m["furnace_lv"]) for m in members]

                            if not members:
                                await interaction.response.send_message(
                                    "❌ No members found in this alliance.", 
                                    ephemeral=True
                                )
                                return

                            max_fl = max(member[2] for member in members)
                            avg_fl = sum(member[2] for member in members) / len(members)

                            
                            member_embed = discord.Embed(
                                title=f"👥 {source_alliance_name} - Member Selection",
                                description=(
                                    "```ml\n"
                                    "Alliance Statistics\n"
                                    "══════════════════════════\n"
                                    f"📊 Total Members    : {len(members)}\n"
                                    f"⚔️ Highest Level    : {self.cog.level_mapping.get(max_fl, str(max_fl))}\n"
                                    f"📈 Average Level    : {self.cog.level_mapping.get(int(avg_fl), str(int(avg_fl)))}\n"
                                    "══════════════════════════\n"
                                    "```\n"
                                    "Select the member to transfer:\n\n"
                                    "**Selection Methods**\n"
                                    "1️⃣ Select member from menu below\n"
                                    "2️⃣ Click 'Select by FID' button and enter FID\n"
                                    "━━━━━━━━━━━━━━━━━━━━━━"
                                ),
                                color=discord.Color.blue()
                            )

                            member_view = MemberSelectView(members, source_alliance_name, self.cog, is_remove_operation=False)
                            
                            async def member_callback(member_interaction: discord.Interaction):
                                selected_fid = int(member_view.current_select.values[0])
                                
                                user_doc = mongo.users.find_one({"fid": selected_fid})
                                selected_member_name = user_doc["nickname"] if user_doc else "Unknown"

                                
                                target_embed = discord.Embed(
                                    title="🎯 Target Alliance Selection",
                                    description=(
                                        f"Select target alliance to transfer "
                                        f"member **{selected_member_name}**:"
                                    ),
                                    color=discord.Color.blue()
                                )

                                target_options = [
                                    discord.SelectOption(
                                        label=f"{name[:50]}",
                                        value=str(alliance_id),
                                        description=f"ID: {alliance_id} | Members: {count}",
                                        emoji="🏰"
                                    ) for alliance_id, name, count in alliances_with_counts
                                    if alliance_id != source_alliance_id
                                ]

                                target_select = discord.ui.Select(
                                    placeholder="🎯 Select target alliance...",
                                    options=target_options
                                )
                                
                                target_view = discord.ui.View()
                                target_view.add_item(target_select)

                                async def target_callback(target_interaction: discord.Interaction):
                                    target_alliance_id = int(target_select.values[0])
                                    
                                    try:
                                        target_alliance_doc = mongo.alliance_list.find_one({"alliance_id": int(target_alliance_id)})
                                        target_alliance_name = target_alliance_doc["name"] if target_alliance_doc else "Unknown"

                                        mongo.users.update_one(
                                            {"fid": selected_fid},
                                            {"$set": {"alliance": int(target_alliance_id)}}
                                        )

                                        success_embed = discord.Embed(
                                            title="✅ Transfer Successful",
                                            description=(
                                                f"👤 **Member:** {selected_member_name}\n"
                                                f"🆔 **FID:** {selected_fid}\n"
                                                f"📤 **Source:** {source_alliance_name}\n"
                                                f"📥 **Target:** {target_alliance_name}"
                                            ),
                                            color=discord.Color.green()
                                        )
                                        
                                        await target_interaction.response.edit_message(
                                            embed=success_embed,
                                            view=None
                                        )
                                        
                                    except Exception as e:
                                        print(f"Transfer error: {e}")
                                        error_embed = discord.Embed(
                                            title="❌ Error",
                                            description="An error occurred during the transfer operation.",
                                            color=discord.Color.red()
                                        )
                                        await target_interaction.response.edit_message(
                                            embed=error_embed,
                                            view=None
                                        )

                                target_select.callback = target_callback
                                await member_interaction.response.edit_message(
                                    embed=target_embed,
                                    view=target_view
                                )

                            member_view.callback = member_callback
                            await interaction.response.edit_message(
                                embed=member_embed,
                                view=member_view
                            )

                        except Exception as e:
                            self.log_message(f"Source callback error: {e}")
                            await interaction.response.send_message(
                                "❌ An error occurred. Please try again.",
                                ephemeral=True
                            )

                    view.callback = source_callback
                    await button_interaction.response.send_message(
                        embed=select_embed,
                        view=view,
                        ephemeral=True
                    )

                except Exception as e:
                    self.log_message(f"Error in transfer_member_button: {e}")
                    await button_interaction.response.send_message(
                        "❌ An error occurred during the transfer operation.",
                        ephemeral=True
                    )

        view = MemberOperationsView(self)
        await interaction.response.edit_message(embed=embed, view=view)

    async def add_user(self, interaction: discord.Interaction, alliance_id: str, ids: str):
        alliance_doc = mongo.alliance_list.find_one({"alliance_id": int(alliance_id)})
        if alliance_doc:
            alliance_name = alliance_doc["name"]
        else:
            await interaction.response.send_message("Alliance not found.", ephemeral=True)
            return

        if not await self.is_admin(interaction.user.id):
            await interaction.response.send_message("You do not have permission to use this command.", ephemeral=True)
            return
        
        # Always add to queue to ensure proper ordering
        queue_position = await self.login_handler.queue_operation({
            'type': 'member_addition',
            'callback': lambda: self._process_add_user(interaction, alliance_id, alliance_name, ids),
            'description': f"Add members to {alliance_name}",
            'alliance_id': alliance_id,
            'interaction': interaction
        })
        
        # Check if we need to show queue message
        queue_info = self.login_handler.get_queue_info()
        # Calculate member count
        member_count = len(ids.split(',') if ',' in ids else ids.split('\n'))
        
        if queue_position > 1:  # Not the first in queue
            queue_embed = discord.Embed(
                title="⏳ Operation Queued",
                description=(
                    f"Another operation is currently in progress.\n\n"
                    f"**Your operation has been queued:**\n"
                    f"📍 Queue Position: `{queue_position}`\n"
                    f"🏰 Alliance: {alliance_name}\n"
                    f"👥 Members to add: {member_count}\n\n"
                    f"You will be notified when your operation starts."
                ),
                color=discord.Color.orange()
            )
            await interaction.response.send_message(embed=queue_embed, ephemeral=True)
        else:
            # First in queue - will start immediately
            total_count = member_count
            embed = discord.Embed(
                title="👥 User Addition Progress", 
                description=f"Processing {total_count} members for **{alliance_name}**...\n\n**Progress:** `0/{total_count}`", 
                color=discord.Color.blue()
            )
            embed.add_field(
                name=f"\n✅ Successfully Added (0/{total_count})", 
                value="-", 
                inline=False
            )
            embed.add_field(
                name=f"❌ Failed (0/{total_count})", 
                value="-", 
                inline=False
            )
            embed.add_field(
                name=f"⚠️ Already Exists (0/{total_count})", 
                value="-", 
                inline=False
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)

    async def _process_add_user(self, interaction: discord.Interaction, alliance_id: str, alliance_name: str, ids: str):
        """Process the actual user addition operation"""
        # Handle both comma-separated and newline-separated FIDs
        if '\n' in ids:
            ids_list = [fid.strip() for fid in ids.split('\n') if fid.strip()]
        else:
            ids_list = [fid.strip() for fid in ids.split(",") if fid.strip()]

        # Pre-check which FIDs already exist in the database
        already_in_db = []
        fids_to_process = []
        
        for fid in ids_list:
            existing = mongo.users.find_one({"fid": int(fid)}, {"nickname": 1})
            if existing:
                # Member already exists in database
                already_in_db.append((fid, existing["nickname"]))
            else:
                # Member doesn't exist at all
                fids_to_process.append(fid)
        
        total_users = len(ids_list)
        self.log_message(f"Pre-check complete: {len(already_in_db)} already exist, {len(fids_to_process)} to process")
        
        # For queued operations, we need to send a new progress embed
        if interaction.response.is_done():
            embed = discord.Embed(
                title="👥 User Addition Progress", 
                description=f"Processing {total_users} members...\n\n**Progress:** `0/{total_users}`", 
                color=discord.Color.blue()
            )
            embed.add_field(
                name=f"✅ Successfully Added (0/{total_users})", 
                value="-", 
                inline=False
            )
            embed.add_field(
                name=f"❌ Failed (0/{total_users})", 
                value="-", 
                inline=False
            )
            embed.add_field(
                name=f"⚠️ Already Exists (0/{total_users})", 
                value="-", 
                inline=False
            )
            message = await interaction.followup.send(embed=embed, ephemeral=True)
        else:
            # For immediate operations, the progress embed is already sent
            message = await interaction.original_response()
            # Get the embed from the existing message
            embed = (await interaction.original_response()).embeds[0]
        
        # Reset rate limit tracking for this operation
        self.login_handler.api1_requests = []
        self.login_handler.api2_requests = []
        
        # Check API availability before starting
        embed.description = "🔍 Checking API availability..."
        await message.edit(embed=embed)
        
        await self.login_handler.check_apis_availability()
        
        if not self.login_handler.available_apis:
            # No APIs available
            embed.description = "❌ Both APIs are unavailable. Cannot proceed."
            embed.color = discord.Color.red()
            await message.edit(embed=embed)
            return
        
        # Get processing rate from login handler
        rate_text = self.login_handler.get_processing_rate()
        
        # Update embed with rate information
        queue_info = f"\n📋 **Operations in queue:** {self.login_handler.get_queue_info()['queue_size']}" if self.login_handler.get_queue_info()['queue_size'] > 0 else ""
        embed.description = f"Processing {total_users} members...\n{rate_text}{queue_info}\n\n**Progress:** `0/{total_users}`"
        embed.color = discord.Color.blue()
        await message.edit(embed=embed)

        added_count = 0
        error_count = 0 
        already_exists_count = len(already_in_db)
        added_users = []
        error_users = []
        already_exists_users = already_in_db.copy()

        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        log_file_path = os.path.join(self.log_directory, 'add_memberlog.txt')
        
        try:
            with open(log_file_path, 'a', encoding='utf-8') as log_file:
                log_file.write(f"\n{'='*50}\n")
                log_file.write(f"Date: {timestamp}\n")
                log_file.write(f"Administrator: {interaction.user.name} (ID: {interaction.user.id})\n")
                log_file.write(f"Alliance: {alliance_name} (ID: {alliance_id})\n")
                log_file.write(f"FIDs to Process: {ids.replace(chr(10), ', ')}\n")
                log_file.write(f"Total Members to Process: {total_users}\n")
                log_file.write(f"API Mode: {self.login_handler.get_mode_text()}\n")
                log_file.write(f"Available APIs: {self.login_handler.available_apis}\n")
                log_file.write(f"Operations in Queue: {self.login_handler.get_queue_info()['queue_size']}\n")
                log_file.write('-'*50 + '\n')

            # Update initial display with pre-existing members
            if already_exists_count > 0:
                embed.set_field_at(
                    2,
                    name=f"⚠️ Already Exists ({already_exists_count}/{total_users})",
                    value="Existing user list cannot be displayed due to exceeding 70 users" if len(already_exists_users) > 70 
                    else ", ".join([n for _, n in already_exists_users]) or "-",
                    inline=False
                )
                await message.edit(embed=embed)
            
            index = 0
            while index < len(fids_to_process):
                fid = fids_to_process[index]
                try:
                    # Update progress
                    queue_info = f"\n📋 **Operations in queue:** {self.login_handler.get_queue_info()['queue_size']}" if self.login_handler.get_queue_info()['queue_size'] > 0 else ""
                    current_progress = already_exists_count + index + 1
                    embed.description = f"Processing {total_users} members...\n{rate_text}{queue_info}\n\n**Progress:** `{current_progress}/{total_users}`"
                    await message.edit(embed=embed)
                    
                    # Fetch player data using login handler
                    result = await self.login_handler.fetch_player_data(fid)
                    
                    with open(log_file_path, 'a', encoding='utf-8') as log_file:
                        log_file.write(f"\nAPI Response for FID {fid}:\n")
                        log_file.write(f"Status: {result['status']}\n")
                        if result.get('api_used'):
                            log_file.write(f"API Used: {result['api_used']}\n")
                    
                    if result['status'] == 'rate_limited':
                        # Handle rate limiting with countdown
                        wait_time = result.get('wait_time', 60)
                        countdown_start = time.time()
                        remaining_time = wait_time
                        
                        with open(log_file_path, 'a', encoding='utf-8') as log_file:
                            log_file.write(f"Rate limit reached - Total wait time: {wait_time:.1f} seconds\n")
                        
                        # Update display with countdown
                        while remaining_time > 0:
                            queue_info = f"\n📋 **Operations in queue:** {self.login_handler.get_queue_info()['queue_size']}" if self.login_handler.get_queue_info()['queue_size'] > 0 else ""
                            embed.description = f"⚠️ Rate limit reached. Waiting {remaining_time:.0f} seconds...{queue_info}"
                            embed.color = discord.Color.orange()
                            await message.edit(embed=embed)
                            
                            # Wait for up to 5 seconds before updating
                            await asyncio.sleep(min(5, remaining_time))
                            elapsed = time.time() - countdown_start
                            remaining_time = max(0, wait_time - elapsed)
                        
                        embed.color = discord.Color.blue()
                        continue  # Retry this request
                    
                    if result['status'] == 'success':
                        data = result['data']
                        with open(log_file_path, 'a', encoding='utf-8') as log_file:
                            log_file.write(f"API Response Data: {str(data)}\n")
                        
                        nickname = data.get('nickname')
                        furnace_lv = data.get('stove_lv', 0)
                        stove_lv_content = data.get('stove_lv_content', None)
                        kid = data.get('kid', None)

                        if nickname:
                            try: # Since we pre-filtered, this FID should not exist in database
                                mongo.users.insert_one({
                                    "fid": int(fid),
                                    "nickname": nickname,
                                    "furnace_lv": furnace_lv,
                                    "kid": kid,
                                    "stove_lv_content": stove_lv_content,
                                    "alliance": int(alliance_id)
                                })
                                
                                with open(self.log_file, 'a', encoding='utf-8') as f:
                                    f.write(f"[{timestamp}] Successfully added member - FID: {fid}, Nickname: {nickname}, Level: {furnace_lv}\n")
                                
                                added_count += 1
                                added_users.append((fid, nickname))
                                
                                embed.set_field_at(
                                    0,
                                    name=f"✅ Successfully Added ({added_count}/{total_users})",
                                    value="User list cannot be displayed due to exceeding 70 users" if len(added_users) > 70 
                                    else ", ".join([n for _, n in added_users]) or "-",
                                    inline=False
                                )
                                await message.edit(embed=embed)
                                
                            except pymongo.errors.DuplicateKeyError as e:
                                # This shouldn't happen since we pre-filtered, but handle it just in case
                                with open(log_file_path, 'a', encoding='utf-8') as log_file:
                                    log_file.write(f"ERROR: Member already exists (race condition?) - FID {fid}: {str(e)}\n")
                                already_exists_count += 1
                                already_exists_users.append((fid, nickname))
                                
                                embed.set_field_at(
                                    2,
                                    name=f"⚠️ Already Exists ({already_exists_count}/{total_users})",
                                    value="Existing user list cannot be displayed due to exceeding 70 users" if len(already_exists_users) > 70 
                                    else ", ".join([n for _, n in already_exists_users]) or "-",
                                    inline=False
                                )
                                await message.edit(embed=embed)
                                
                            except Exception as e:
                                with open(log_file_path, 'a', encoding='utf-8') as log_file:
                                    log_file.write(f"ERROR: Database error for FID {fid}: {str(e)}\n")
                                error_count += 1
                                error_users.append(fid)
                                
                                embed.set_field_at(
                                    1,
                                    name=f"❌ Failed ({error_count}/{total_users})",
                                    value="Error list cannot be displayed due to exceeding 70 users" if len(error_users) > 70 
                                    else ", ".join(error_users) or "-",
                                    inline=False
                                )
                                await message.edit(embed=embed)
                        else:
                            # No nickname in API response
                            error_count += 1
                            error_users.append(fid)
                    else:
                            # Handle other error statuses
                            error_msg = result.get('error_message', 'Unknown error')
                            with open(log_file_path, 'a', encoding='utf-8') as log_file:
                                log_file.write(f"ERROR: {error_msg} for FID {fid}\n")
                            error_count += 1
                            if fid not in error_users:
                                error_users.append(fid)
                            embed.set_field_at(
                                1,
                                name=f"❌ Failed ({error_count}/{total_users})",
                                value="Error list cannot be displayed due to exceeding 70 users" if len(error_users) > 70 
                                else ", ".join(error_users) or "-",
                                inline=False
                            )
                            await message.edit(embed=embed)
                    
                    index += 1

                except Exception as e:
                    with open(log_file_path, 'a', encoding='utf-8') as log_file:
                        log_file.write(f"ERROR: Request failed for FID {fid}: {str(e)}\n")
                        error_count += 1
                        error_users.append(fid)
                        await message.edit(embed=embed)
                        index += 1

            embed.set_field_at(0, name=f"✅ Successfully Added ({added_count}/{total_users})",
                value="User list cannot be displayed due to exceeding 70 users" if len(added_users) > 70 
                else ", ".join([nickname for _, nickname in added_users]) or "-",
                inline=False
            )
            
            embed.set_field_at(1, name=f"❌ Failed ({error_count}/{total_users})",
                value="Error list cannot be displayed due to exceeding 70 users" if len(error_users) > 70 
                else ", ".join(error_users) or "-",
                inline=False
            )
            
            embed.set_field_at(2, name=f"⚠️ Already Exists ({already_exists_count}/{total_users})",
                value="Existing user list cannot be displayed due to exceeding 70 users" if len(already_exists_users) > 70 
                else ", ".join([nickname for _, nickname in already_exists_users]) or "-",
                inline=False
            )

            await message.edit(embed=embed)

            try:
                alliance_log_result = mongo.alliance_logs.find_one({"alliance_id": int(alliance_id)})
                
                if alliance_log_result and alliance_log_result.get("channel_id"):
                    log_embed = discord.Embed(
                        title="👥 Members Added to Alliance",
                        description=(
                            f"**Alliance:** {alliance_name}\n"
                            f"**Administrator:** {interaction.user.name} (`{interaction.user.id}`)\n"
                            f"**Date:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
                            f"**Results:**\n"
                            f"✅ Successfully Added: {added_count}\n"
                            f"❌ Failed: {error_count}\n"
                            f"⚠️ Already Exists: {already_exists_count}\n\n"
                            "**Added FIDs:**\n"
                            f"```\n{', '.join(ids_list)}\n```"
                        ),
                        color=discord.Color.green()
                    )

                    try:
                        alliance_channel_id = int(alliance_log_result["channel_id"])
                        alliance_log_channel = self.bot.get_channel(alliance_channel_id)
                        if alliance_log_channel:
                            await alliance_log_channel.send(embed=log_embed)
                    except Exception as e:
                        with open(log_file_path, 'a', encoding='utf-8') as log_file:
                            log_file.write(f"ERROR: Alliance Log Sending Error: {str(e)}\n")

            except Exception as e:
                with open(log_file_path, 'a', encoding='utf-8') as log_file:
                    log_file.write(f"ERROR: Log record error: {str(e)}\n")

            with open(log_file_path, 'a', encoding='utf-8') as log_file:
                log_file.write(f"\nFinal Results:\n")
                log_file.write(f"Successfully Added: {added_count}\n")
                log_file.write(f"Failed: {error_count}\n")
                log_file.write(f"Already Exists: {already_exists_count}\n")
                log_file.write(f"API Mode: {self.login_handler.get_mode_text()}\n")
                log_file.write(f"API1 Requests: {len(self.login_handler.api1_requests)}\n")
                log_file.write(f"API2 Requests: {len(self.login_handler.api2_requests)}\n")
                log_file.write(f"{'='*50}\n")

        except Exception as e:
            with open(log_file_path, 'a', encoding='utf-8') as log_file:
                log_file.write(f"CRITICAL ERROR: {str(e)}\n")
                log_file.write(f"{'='*50}\n")

        # Calculate total processing time
        end_time = datetime.now()
        start_time = datetime.strptime(timestamp, '%Y-%m-%d %H:%M:%S')
        processing_time = (end_time - start_time).total_seconds()
        
        queue_info = f"📋 **Operations still in queue:** {self.login_handler.get_queue_info()['queue_size']}" if self.login_handler.get_queue_info()['queue_size'] > 0 else ""
        
        embed.title = "✅ User Addition Completed"
        embed.description = (
            f"Process completed for {total_users} members.\n"
            f"**Processing Time:** {processing_time:.1f} seconds{queue_info}\n\n"
        )
        embed.color = discord.Color.green()
        await message.edit(embed=embed)

    async def is_admin(self, user_id):
        try:
            admin = mongo.admin.find_one({"id": user_id})
            return admin is not None
        except Exception as e:
            self.log_message(f"Error in admin check: {str(e)}")
            self.log_message(f"Error details: {str(e.__class__.__name__)}")
            return False

    def cog_unload(self):
        pass

    async def get_admin_alliances(self, user_id: int, guild_id: int):
        try:
            admin = mongo.admin.find_one({"id": user_id})
            if not admin:
                self.log_message(f"User {user_id} is not an admin")
                return [], [], False
            
            is_initial = admin.get("is_initial", 0)
            
            if is_initial == 1:
                alliances = list(mongo.alliance_list.find({}, {"alliance_id": 1, "name": 1}).sort("name", 1))
                return [(a["alliance_id"], a["name"]) for a in alliances], [], True
            
            server_alliances_docs = list(mongo.alliance_list.find({"discord_server_id": guild_id}, {"alliance_id": 1, "name": 1}).sort("name", 1))
            server_alliances = [(a["alliance_id"], a["name"]) for a in server_alliances_docs]
            
            special_alliance_ids_docs = list(mongo.adminserver.find({"admin": user_id}, {"alliances_id": 1}))
            special_alliance_ids = [d["alliances_id"] for d in special_alliance_ids_docs]
            
            special_alliances = []
            if special_alliance_ids:
                special_alliances_docs = list(mongo.alliance_list.find({"alliance_id": {"$in": special_alliance_ids}}, {"alliance_id": 1, "name": 1}).sort("name", 1))
                special_alliances = [(a["alliance_id"], a["name"]) for a in special_alliances_docs]
            
            all_alliances = list(set(server_alliances + special_alliances))
            
            if not all_alliances and not special_alliances:
                return [], [], False
            
            return all_alliances, special_alliances, False
            
        except Exception as e:
            return [], [], False

    async def handle_button_interaction(self, interaction: discord.Interaction):
        custom_id = interaction.data["custom_id"]
        
        if custom_id == "main_menu":
            await self.show_main_menu(interaction)
    
    async def show_main_menu(self, interaction: discord.Interaction):
        try:
            alliance_cog = self.bot.get_cog("Alliance")
            if alliance_cog:
                await alliance_cog.show_main_menu(interaction)
            else:
                await interaction.response.send_message(
                    "❌ An error occurred while returning to main menu.",
                    ephemeral=True
                )
        except Exception as e:
            self.log_message(f"[ERROR] Main Menu error in member operations: {e}")
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    "❌ An error occurred while returning to main menu.", 
                    ephemeral=True
                )
            else:
                await interaction.followup.send(
                    "❌ An error occurred while returning to main menu.",
                    ephemeral=True
                )

class AddMemberModal(discord.ui.Modal):
    def __init__(self, alliance_id):
        super().__init__(title="Add Member")
        self.alliance_id = alliance_id
        self.add_item(discord.ui.TextInput(
            label="Enter FIDs (comma or newline separated)", 
            placeholder="Comma: 12345,67890,54321\nNewline:\n12345\n67890\n54321",
            style=discord.TextStyle.paragraph
        ))

    async def on_submit(self, interaction: discord.Interaction):
        try:
            ids = self.children[0].value
            await interaction.client.get_cog("AllianceMemberOperations").add_user(
                interaction, 
                self.alliance_id, 
                ids
            )
        except Exception as e:
            print(f"ERROR: Modal submit error - {str(e)}")
            await interaction.response.send_message(
                "An error occurred. Please try again.", 
                ephemeral=True
            )

class AllianceSelectView(discord.ui.View):
    def __init__(self, alliances_with_counts, cog=None, page=0, context="transfer"):
        super().__init__(timeout=7200)
        self.alliances = alliances_with_counts
        self.cog = cog
        self.page = page
        self.max_page = (len(alliances_with_counts) - 1) // 25 if alliances_with_counts else 0
        self.current_select = None
        self.callback = None
        self.member_dict = {}
        self.selected_alliance_id = None
        self.context = context  # "transfer", "furnace_history", or "nickname_history"
        self.update_select_menu()

    def update_select_menu(self):
        for item in self.children[:]:
            if isinstance(item, discord.ui.Select):
                self.remove_item(item)

        start_idx = self.page * 25
        end_idx = min(start_idx + 25, len(self.alliances))
        current_alliances = self.alliances[start_idx:end_idx]

        select = discord.ui.Select(
            placeholder=f"🏰 Select an alliance... (Page {self.page + 1}/{self.max_page + 1})",
            options=[
                discord.SelectOption(
                    label=f"{name[:50]}",
                    value=str(alliance_id),
                    description=f"ID: {alliance_id} | Members: {count}",
                    emoji="🏰"
                ) for alliance_id, name, count in current_alliances
            ]
        )
        
        async def select_callback(interaction: discord.Interaction):
            self.current_select = select
            if self.callback:
                await self.callback(interaction)
        
        select.callback = select_callback
        self.add_item(select)
        self.current_select = select

        if hasattr(self, 'prev_button'):
            self.prev_button.disabled = self.page == 0
        if hasattr(self, 'next_button'):
            self.next_button.disabled = self.page == self.max_page

    @discord.ui.button(label="◀️", style=discord.ButtonStyle.secondary)
    async def prev_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.page = max(0, self.page - 1)
        self.update_select_menu()
        await interaction.response.edit_message(view=self)

    @discord.ui.button(label="▶️", style=discord.ButtonStyle.secondary)
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.page = min(self.max_page, self.page + 1)
        self.update_select_menu()
        await interaction.response.edit_message(view=self)

    @discord.ui.button(label="Select by FID", emoji="🔍", style=discord.ButtonStyle.secondary)
    async def fid_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            if self.current_select and self.current_select.values:
                self.selected_alliance_id = self.current_select.values[0]
            
            modal = FIDSearchModal(
                selected_alliance_id=self.selected_alliance_id,
                alliances=self.alliances,
                callback=self.callback,
                context=self.context,
                cog=self.cog
            )
            await interaction.response.send_modal(modal)
        except Exception as e:
            print(f"FID button error: {e}")
            await interaction.response.send_message(
                "❌ An error has occurred. Please try again.",
                ephemeral=True
            )

class FIDSearchModal(discord.ui.Modal):
    def __init__(self, selected_alliance_id=None, alliances=None, callback=None, context="transfer", cog=None):
        super().__init__(title="Search Members with FID")
        self.selected_alliance_id = selected_alliance_id
        self.alliances = alliances
        self.callback = callback
        self.context = context
        self.cog = cog
        
        self.add_item(discord.ui.TextInput(
            label="Member ID",
            placeholder="Example: 12345",
            min_length=1,
            max_length=20,
            required=True
        ))

    async def on_submit(self, interaction: discord.Interaction):
        try:
            fid = self.children[0].value.strip()
            
            # Check if we're in a history context
            if self.context in ["furnace_history", "nickname_history"]:
                # Get the Changes cog
                changes_cog = self.cog.bot.get_cog("Changes") if self.cog else interaction.client.get_cog("Changes")
                if changes_cog:
                    await interaction.response.defer()
                    if self.context == "furnace_history":
                        await changes_cog.show_furnace_history(interaction, int(fid))
                    else:
                        await changes_cog.show_nickname_history(interaction, int(fid))
                else:
                    await interaction.response.send_message(
                        "❌ History feature is not available.",
                        ephemeral=True
                    )
                return
            
            # Original transfer logic
            user_doc = mongo.users.find_one({"fid": int(fid)})
            
            if not user_doc:
                await interaction.response.send_message(
                    "❌ No member with this FID was found.",
                    ephemeral=True
                )
                return

            fid = user_doc["fid"]
            nickname = user_doc["nickname"]
            furnace_lv = user_doc["furnace_lv"]
            current_alliance_id = user_doc["alliance"]
 
            alliance_doc = mongo.alliance_list.find_one({"alliance_id": int(current_alliance_id)})
            current_alliance_name = alliance_doc["name"] if alliance_doc else "Unknown"

            embed = discord.Embed(
                title="✅ Member Found - Transfer Process",
                description=(
                    f"**Member Information:**\n"
                    f"👤 **Name:** {nickname}\n"
                    f"🆔 **FID:** {fid}\n"
                    f"⚔️ **Level:** {furnace_lv}\n"
                    f"🏰 **Current Alliance:** {current_alliance_name}\n\n"
                    "**Transfer Process**\n"
                    "Please select the alliance you want to transfer the member to:"
                ),
                color=discord.Color.blue()
            )

            select = discord.ui.Select(
                placeholder="🎯 Choose the target alliance...",
                options=[
                    discord.SelectOption(
                        label=f"{name[:50]}",
                        value=str(alliance_id),
                        description=f"ID: {alliance_id}",
                        emoji="🏰"
                    ) for alliance_id, name, _ in self.alliances
                    if alliance_id != current_alliance_id  
                ]
            )
            
            view = discord.ui.View()
            view.add_item(select)

            async def select_callback(select_interaction: discord.Interaction):
                target_alliance_id = int(select.values[0])
                
                try:
                    target_alliance_doc = mongo.alliance_list.find_one({"alliance_id": int(target_alliance_id)})
                    target_alliance_name = target_alliance_doc["name"] if target_alliance_doc else "Unknown"

                    mongo.users.update_one(
                        {"fid": int(fid)},
                        {"$set": {"alliance": int(target_alliance_id)}}
                    )

                    
                    success_embed = discord.Embed(
                        title="✅ Transfer Successful",
                        description=(
                            f"👤 **Member:** {nickname}\n"
                            f"🆔 **FID:** {fid}\n"
                            f"📤 **Source:** {current_alliance_name}\n"
                            f"📥 **Target:** {target_alliance_name}"
                        ),
                        color=discord.Color.green()
                    )
                    
                    await select_interaction.response.edit_message(
                        embed=success_embed,
                        view=None
                    )
                    
                except Exception as e:
                    print(f"Transfer error: {e}")
                    error_embed = discord.Embed(
                        title="❌ Error",
                        description="An error occurred during the transfer operation.",
                        color=discord.Color.red()
                    )
                    await select_interaction.response.edit_message(
                        embed=error_embed,
                        view=None
                    )

            select.callback = select_callback
            await interaction.response.send_message(
                embed=embed,
                view=view,
                ephemeral=True
            )

        except Exception as e:
            print(f"Error details: {str(e.__class__.__name__)}")
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    "❌ An error has occurred. Please try again.",
                    ephemeral=True
                )

class MemberSelectView(discord.ui.View):
    def __init__(self, members, source_alliance_name, cog, page=0, is_remove_operation=False):
        super().__init__(timeout=7200)
        self.members = members
        self.source_alliance_name = source_alliance_name
        self.cog = cog
        self.page = page
        self.max_page = (len(members) - 1) // 25
        self.current_select = None
        self.callback = None
        self.member_dict = {str(fid): nickname for fid, nickname, _ in members}
        self.selected_alliance_id = None
        self.alliances = None
        self.is_remove_operation = is_remove_operation
        self.update_select_menu()

    def update_select_menu(self):
        for item in self.children[:]:
            if isinstance(item, discord.ui.Select):
                self.remove_item(item)

        start_idx = self.page * 25
        end_idx = min(start_idx + 25, len(self.members))
        current_members = self.members[start_idx:end_idx]

        options = []
        
        if self.page == 0:
            options.append(discord.SelectOption(
                label="ALL MEMBERS",
                value="all",
                description=f"⚠️ Delete all {len(self.members)} members!",
                emoji="⚠️"
            ))

        remaining_slots = 25 - len(options)
        member_options = [
            discord.SelectOption(
                label=f"{nickname[:50]}",
                value=str(fid),
                description=f"FID: {fid} | FC: {self.cog.level_mapping.get(furnace_lv, str(furnace_lv))}",
                emoji="👤"
            ) for fid, nickname, furnace_lv in current_members[:remaining_slots]
        ]
        options.extend(member_options)

        # Determine placeholder based on context (remove vs transfer)
        placeholder_text = "👤 Select member to remove..." if hasattr(self, 'is_remove_operation') and self.is_remove_operation else "👤 Select member to transfer..."

        select = discord.ui.Select(
            placeholder=f"{placeholder_text} (Page {self.page + 1}/{self.max_page + 1})",
            options=options
        )
        
        async def select_callback(interaction: discord.Interaction):
            self.current_select = select
            if self.callback:
                await self.callback(interaction)
        
        select.callback = select_callback
        self.add_item(select)
        self.current_select = select

        if hasattr(self, 'prev_button'):
            self.prev_button.disabled = self.page == 0
        if hasattr(self, 'next_button'):
            self.next_button.disabled = self.page == self.max_page

    @discord.ui.button(label="◀️", style=discord.ButtonStyle.secondary)
    async def prev_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.page = max(0, self.page - 1)
        self.update_select_menu()
        await interaction.response.edit_message(view=self)

    @discord.ui.button(label="▶️", style=discord.ButtonStyle.secondary)
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.page = min(self.max_page, self.page + 1)
        self.update_select_menu()
        await interaction.response.edit_message(view=self)

    @discord.ui.button(label="Select by FID", emoji="🔍", style=discord.ButtonStyle.secondary)
    async def fid_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            
            if self.current_select and self.current_select.values:
                self.selected_alliance_id = self.current_select.values[0]
            
            modal = FIDSearchModal(
                selected_alliance_id=self.selected_alliance_id,
                alliances=self.alliances,
                callback=self.callback,
                context=self.context,
                cog=self.cog
            )
            await interaction.response.send_modal(modal)
        except Exception as e:
            print(f"FID button error: {e}")
            await interaction.response.send_message(
                "❌ An error has occurred. Please try again.",
                ephemeral=True
            )

async def setup(bot):
    await bot.add_cog(AllianceMemberOperations(bot))