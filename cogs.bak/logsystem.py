import discord
from discord.ext import commands
from db.mongo_adapter import mongo
from datetime import datetime
from .alliance_member_operations import AllianceSelectView
from .alliance import PaginatedChannelView

class LogSystem(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # Database setup is handled by MongoAdapter

    @commands.Cog.listener()
    async def on_interaction(self, interaction: discord.Interaction):
        if not interaction.type == discord.InteractionType.component:
            return

        custom_id = interaction.data.get("custom_id", "")
        
        if custom_id == "log_system":
            try:
                admin = mongo.admin.find_one({"id": interaction.user.id})
                
                if not admin or admin.get("is_initial", 0) != 1:
                    await interaction.response.send_message(
                        "❌ Only global administrators can access the log system.", 
                        ephemeral=True
                    )
                    return

                log_embed = discord.Embed(
                    title="📋 Alliance Log System",
                    description=(
                        "Select an option to manage alliance logs:\n\n"
                        "**Available Options**\n"
                        "━━━━━━━━━━━━━━━━━━━━━━\n"
                        "📝 **Set Log Channel**\n"
                        "└ Assign a log channel to an alliance\n\n"
                        "🗑️ **Remove Log Channel**\n"
                        "└ Remove alliance log channel\n\n"
                        "📊 **View Log Channels**\n"
                        "└ List all alliance log channels\n"
                        "━━━━━━━━━━━━━━━━━━━━━━"
                    ),
                    color=discord.Color.blue()
                )

                view = discord.ui.View()
                view.add_item(discord.ui.Button(
                    label="Set Log Channel",
                    emoji="📝",
                    style=discord.ButtonStyle.primary,
                    custom_id="set_log_channel",
                    row=0
                ))
                view.add_item(discord.ui.Button(
                    label="Remove Log Channel",
                    emoji="🗑️",
                    style=discord.ButtonStyle.danger,
                    custom_id="remove_log_channel",
                    row=0
                ))
                view.add_item(discord.ui.Button(
                    label="View Log Channels",
                    emoji="📊",
                    style=discord.ButtonStyle.secondary,
                    custom_id="view_log_channels",
                    row=1
                ))
                view.add_item(discord.ui.Button(
                    label="Back",
                    emoji="◀️",
                    style=discord.ButtonStyle.secondary,
                    custom_id="bot_operations",
                    row=2
                ))

                await interaction.response.send_message(
                    embed=log_embed,
                    view=view,
                    ephemeral=True
                )

            except Exception as e:
                print(f"Error in log system menu: {e}")
                await interaction.response.send_message(
                    "❌ An error occurred while accessing the log system.",
                    ephemeral=True
                )

        elif custom_id == "set_log_channel":
            try:
                admin = mongo.admin.find_one({"id": interaction.user.id})
                
                if not admin or admin.get("is_initial", 0) != 1:
                    await interaction.response.send_message(
                        "❌ Only global administrators can set log channels.", 
                        ephemeral=True
                    )
                    return

                alliances = list(mongo.alliance_list.find({}, {"alliance_id": 1, "name": 1}).sort("name", 1))
                alliances = [(a["alliance_id"], a["name"]) for a in alliances]

                if not alliances:
                    await interaction.response.send_message(
                        "❌ No alliances found.", 
                        ephemeral=True
                    )
                    return

                alliances_with_counts = []
                for alliance_id, name in alliances:
                    member_count = mongo.users.count_documents({"alliance": int(alliance_id)})
                    alliances_with_counts.append((alliance_id, name, member_count))

                alliance_embed = discord.Embed(
                    title="📝 Set Log Channel",
                    description=(
                        "Please select an alliance:\n\n"
                        "**Alliance List**\n"
                        "━━━━━━━━━━━━━━━━━━━━━━\n"
                        "Select an alliance from the list below:\n"
                    ),
                    color=discord.Color.blue()
                )

                view = AllianceSelectView(alliances_with_counts, self)
                view.callback = lambda i: alliance_callback(i, view)

                async def alliance_callback(select_interaction: discord.Interaction, alliance_view):
                    try:
                        alliance_id = int(alliance_view.current_select.values[0])
                        
                        channel_embed = discord.Embed(
                            title="📝 Set Log Channel",
                            description=(
                                "**Instructions:**\n"
                                "━━━━━━━━━━━━━━━━━━━━━━\n"
                                "Please select a channel for logging\n\n"
                                "**Page:** 1/1\n"
                                f"**Total Channels:** {len(select_interaction.guild.text_channels)}"
                            ),
                            color=discord.Color.blue()
                        )

                        async def channel_select_callback(channel_interaction: discord.Interaction):
                            try:
                                channel_id = int(channel_interaction.data["values"][0])
                                
                                mongo.alliance_logs.update_one(
                                    {"alliance_id": int(alliance_id)},
                                    {"$set": {"channel_id": channel_id}},
                                    upsert=True
                                )

                                alliance_doc = mongo.alliance_list.find_one({"alliance_id": int(alliance_id)})
                                alliance_name = alliance_doc["name"] if alliance_doc else "Unknown"

                                success_embed = discord.Embed(
                                    title="✅ Log Channel Set",
                                    description=(
                                        f"Successfully set log channel:\n\n"
                                        f"🏰 **Alliance:** {alliance_name}\n"
                                        f"📝 **Channel:** <#{channel_id}>\n"
                                    ),
                                    color=discord.Color.green()
                                )

                                await channel_interaction.response.edit_message(
                                    embed=success_embed,
                                    view=None
                                )

                            except Exception as e:
                                print(f"Error setting log channel: {e}")
                                await channel_interaction.response.send_message(
                                    "❌ An error occurred while setting the log channel.",
                                    ephemeral=True
                                )

                        channels = select_interaction.guild.text_channels
                        channel_view = PaginatedChannelView(channels, channel_select_callback)

                        if not select_interaction.response.is_done():
                            await select_interaction.response.edit_message(
                                embed=channel_embed,
                                view=channel_view
                            )
                        else:
                            await select_interaction.message.edit(
                                embed=channel_embed,
                                view=channel_view
                            )

                    except Exception as e:
                        print(f"Error in alliance selection: {e}")
                        if not select_interaction.response.is_done():
                            await select_interaction.response.send_message(
                                "❌ An error occurred while processing your selection.",
                                ephemeral=True
                            )
                        else:
                            await select_interaction.followup.send(
                                "❌ An error occurred while processing your selection.",
                                ephemeral=True
                            )

                await interaction.response.send_message(
                    embed=alliance_embed,
                    view=view,
                    ephemeral=True
                )

            except Exception as e:
                print(f"Error in set log channel: {e}")
                await interaction.response.send_message(
                    "❌ An error occurred while setting up the log channel.",
                    ephemeral=True
                )

        elif custom_id == "remove_log_channel":
            try:
                admin = mongo.admin.find_one({"id": interaction.user.id})
                
                if not admin or admin.get("is_initial", 0) != 1:
                    await interaction.response.send_message(
                        "❌ Only global administrators can remove log channels.", 
                        ephemeral=True
                    )
                    return

                log_entries_docs = list(mongo.alliance_logs.find({}, {"alliance_id": 1, "channel_id": 1}))
                log_entries = [(d["alliance_id"], d["channel_id"]) for d in log_entries_docs]

                if not log_entries:
                    await interaction.response.send_message(
                        "❌ No alliance log channels found.", 
                        ephemeral=True
                    )
                    return

                alliances_with_counts = []
                for alliance_id, channel_id in log_entries:
                    alliance_doc = mongo.alliance_list.find_one({"alliance_id": int(alliance_id)})
                    alliance_name = alliance_doc["name"] if alliance_doc else "Unknown Alliance"

                    member_count = mongo.users.count_documents({"alliance": int(alliance_id)})
                    alliances_with_counts.append((alliance_id, alliance_name, member_count))

                if not alliances_with_counts:
                    await interaction.response.send_message(
                        "❌ No valid log channels found.", 
                        ephemeral=True
                    )
                    return

                remove_embed = discord.Embed(
                    title="🗑️ Remove Log Channel",
                    description=(
                        "Select an alliance to remove its log channel:\n\n"
                        "**Current Log Channels**\n"
                        "━━━━━━━━━━━━━━━━━━━━━━\n"
                        "Select an alliance from the list below:\n"
                    ),
                    color=discord.Color.red()
                )

                view = AllianceSelectView(alliances_with_counts, self)

                async def alliance_callback(select_interaction: discord.Interaction):
                    try:
                        alliance_id = int(view.current_select.values[0])
                        
                        alliance_doc = mongo.alliance_list.find_one({"alliance_id": int(alliance_id)})
                        alliance_name = alliance_doc["name"] if alliance_doc else "Unknown"
                        
                        log_entry = mongo.alliance_logs.find_one({"alliance_id": int(alliance_id)})
                        channel_id = log_entry["channel_id"] if log_entry else None
                        
                        confirm_embed = discord.Embed(
                            title="⚠️ Confirm Removal",
                            description=(
                                f"Are you sure you want to remove the log channel for:\n\n"
                                f"🏰 **Alliance:** {alliance_name}\n"
                                f"📝 **Channel:** <#{channel_id}>\n\n"
                                "This action cannot be undone!"
                            ),
                            color=discord.Color.yellow()
                        )

                        confirm_view = discord.ui.View()
                        
                        async def confirm_callback(button_interaction: discord.Interaction):
                            try:
                                mongo.alliance_logs.delete_one({"alliance_id": int(alliance_id)})

                                success_embed = discord.Embed(
                                    title="✅ Log Channel Removed",
                                    description=(
                                        f"Successfully removed log channel for:\n\n"
                                        f"🏰 **Alliance:** {alliance_name}\n"
                                        f"📝 **Channel:** <#{channel_id}>"
                                    ),
                                    color=discord.Color.green()
                                )

                                await button_interaction.response.edit_message(
                                    embed=success_embed,
                                    view=None
                                )

                            except Exception as e:
                                print(f"Error removing log channel: {e}")
                                await button_interaction.response.send_message(
                                    "❌ An error occurred while removing the log channel.",
                                    ephemeral=True
                                )

                        async def cancel_callback(button_interaction: discord.Interaction):
                            cancel_embed = discord.Embed(
                                title="❌ Removal Cancelled",
                                description="The log channel removal has been cancelled.",
                                color=discord.Color.red()
                            )
                            await button_interaction.response.edit_message(
                                embed=cancel_embed,
                                view=None
                            )

                        confirm_button = discord.ui.Button(
                            label="Confirm",
                            emoji="✅",
                            style=discord.ButtonStyle.danger,
                            custom_id="confirm_remove"
                        )
                        confirm_button.callback = confirm_callback

                        cancel_button = discord.ui.Button(
                            label="Cancel",
                            emoji="❌",
                            style=discord.ButtonStyle.secondary,
                            custom_id="cancel_remove"
                        )
                        cancel_button.callback = cancel_callback

                        confirm_view.add_item(confirm_button)
                        confirm_view.add_item(cancel_button)

                        if not select_interaction.response.is_done():
                            await select_interaction.response.edit_message(
                                embed=confirm_embed,
                                view=confirm_view
                            )
                        else:
                            await select_interaction.message.edit(
                                embed=confirm_embed,
                                view=confirm_view
                            )

                    except Exception as e:
                        print(f"Error in alliance selection: {e}")
                        if not select_interaction.response.is_done():
                            await select_interaction.response.send_message(
                                "❌ An error occurred while processing your selection.",
                                ephemeral=True
                            )
                        else:
                            await select_interaction.followup.send(
                                "❌ An error occurred while processing your selection.",
                                ephemeral=True
                            )

                view.callback = alliance_callback

                await interaction.response.send_message(
                    embed=remove_embed,
                    view=view,
                    ephemeral=True
                )

            except Exception as e:
                print(f"Error in remove log channel: {e}")
                await interaction.response.send_message(
                    "❌ An error occurred while setting up the removal menu.",
                    ephemeral=True
                )

        elif custom_id == "view_log_channels":
            try:
                admin = mongo.admin.find_one({"id": interaction.user.id})
                
                if not admin or admin.get("is_initial", 0) != 1:
                    await interaction.response.send_message(
                        "❌ Only global administrators can view log channels.", 
                        ephemeral=True
                    )
                    return

                log_entries_docs = list(mongo.alliance_logs.find({}, {"alliance_id": 1, "channel_id": 1}).sort("alliance_id", 1))
                log_entries = [(d["alliance_id"], d["channel_id"]) for d in log_entries_docs]

                if not log_entries:
                    await interaction.response.send_message(
                        "❌ No alliance log channels found.", 
                        ephemeral=True
                    )
                    return

                list_embed = discord.Embed(
                    title="📊 Alliance Log Channels",
                    description="Current log channel assignments:\n\n",
                    color=discord.Color.blue()
                )

                for alliance_id, channel_id in log_entries:
                    alliance_doc = mongo.alliance_list.find_one({"alliance_id": int(alliance_id)})
                    alliance_name = alliance_doc["name"] if alliance_doc else "Unknown Alliance"

                    channel = interaction.guild.get_channel(channel_id)
                    channel_name = channel.name if channel else "Unknown Channel"

                    list_embed.add_field(
                        name=f"🏰 Alliance ID: {alliance_id}",
                        value=(
                            f"**Name:** {alliance_name}\n"
                            f"**Log Channel:** <#{channel_id}>\n"
                            f"**Channel ID:** {channel_id}\n"
                            f"**Channel Name:** #{channel_name}\n"
                            "━━━━━━━━━━━━━━━━━━━━━━"
                        ),
                        inline=False
                    )

                view = discord.ui.View()
                view.add_item(discord.ui.Button(
                    label="Back",
                    emoji="◀️",
                    style=discord.ButtonStyle.secondary,
                    custom_id="log_system",
                    row=0
                ))

                await interaction.response.send_message(
                    embed=list_embed,
                    view=view,
                    ephemeral=True
                )

            except Exception as e:
                print(f"Error in view log channels: {e}")
                await interaction.response.send_message(
                    "❌ An error occurred while viewing log channels.",
                    ephemeral=True
                )

async def setup(bot):
    await bot.add_cog(LogSystem(bot))
