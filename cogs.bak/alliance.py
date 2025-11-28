import discord
from discord import app_commands
from discord.ext import commands
from db.mongo_adapter import mongo  
import asyncio
from datetime import datetime

class Alliance(commands.Cog):
    def __init__(self, bot):
        self.bot = bot



    async def view_alliances(self, interaction: discord.Interaction):
        
        if interaction.guild is None:
            await interaction.response.send_message("❌ This command must be used in a server, not in DMs.", ephemeral=True)
            return

        user_id = interaction.user.id
        user_id = interaction.user.id
        admin = mongo.admin.find_one({"id": user_id})

        if admin is None:
            await interaction.response.send_message("You do not have permission to view alliances.", ephemeral=True)
            return

        is_initial = admin.get("is_initial", 0)
        guild_id = interaction.guild.id

        try:
            pipeline = []
            if is_initial != 1:
                pipeline.append({"$match": {"discord_server_id": guild_id}})
            
            pipeline.extend([
                {"$lookup": {
                    "from": "alliancesettings",
                    "localField": "alliance_id",
                    "foreignField": "alliance_id",
                    "as": "settings"
                }},
                {"$unwind": {"path": "$settings", "preserveNullAndEmptyArrays": True}},
                {"$sort": {"alliance_id": 1}},
                {"$project": {
                    "alliance_id": 1,
                    "name": 1,
                    "interval": {"$ifNull": ["$settings.interval", 0]}
                }}
            ])

            alliances = list(mongo.alliance_list.aggregate(pipeline))

            alliance_list = ""
            for alliance in alliances:
                alliance_id = alliance["alliance_id"]
                name = alliance["name"]
                interval = alliance["interval"]
                
                member_count = mongo.users.count_documents({"alliance": alliance_id})
                
                interval_text = f"{interval} minutes" if interval > 0 else "No automatic control"
                alliance_list += f"🛡️ **{alliance_id}: {name}**\n👥 Members: {member_count}\n⏱️ Control Interval: {interval_text}\n\n"

            if not alliance_list:
                alliance_list = "No alliances found."

            embed = discord.Embed(
                title="Existing Alliances",
                description=alliance_list,
                color=discord.Color.blue()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)

        except Exception as e:
            await interaction.response.send_message(
                "An error occurred while fetching alliances.", 
                ephemeral=True
            )

    async def alliance_autocomplete(self, interaction: discord.Interaction, current: str):
        alliances = list(mongo.alliance_list.find({}, {"alliance_id": 1, "name": 1}))
        return [
            app_commands.Choice(name=f"{alliance['name']} (ID: {alliance['alliance_id']})", value=str(alliance['alliance_id']))
            for alliance in alliances if current.lower() in alliance['name'].lower()
        ][:25]

    @app_commands.command(name="settings", description="Open settings menu.")
    async def settings(self, interaction: discord.Interaction):
        try:
            if interaction.guild is not None: # Check bot permissions only if in a guild
                perm_check = interaction.guild.get_member(interaction.client.user.id)
                if not perm_check.guild_permissions.administrator:
                    await interaction.response.send_message(
                        "Beeb boop 🤖 I need **Administrator** permissions to function. "
                        "Go to server settings --> Roles --> find my role --> scroll down and turn on Administrator", 
                        ephemeral=True
                    )
                    return
                
            admin_count = mongo.admin.count_documents({})

            user_id = interaction.user.id

            if admin_count == 0:
                mongo.admin.insert_one({"id": user_id, "is_initial": 1})

                first_use_embed = discord.Embed(
                    title="🎉 First Time Setup",
                    description=(
                        "This command has been used for the first time and no administrators were found.\n\n"
                        f"**{interaction.user.name}** has been added as the Global Administrator.\n\n"
                        "You can now access all administrative functions."
                    ),
                    color=discord.Color.green()
                )
                await interaction.response.send_message(embed=first_use_embed, ephemeral=True)
                
                await asyncio.sleep(3)
                
            admin = mongo.admin.find_one({"id": user_id})

            if admin is None:
                await interaction.response.send_message(
                    "You do not have permission to access this menu.", 
                    ephemeral=True
                )
                return

            embed = discord.Embed(
                title="⚙️ Settings Menu",
                description=(
                    "Please select a category:\n\n"
                    "**Menu Categories**\n"
                    "━━━━━━━━━━━━━━━━━━━━━━\n"
                    "🏰 **Alliance Operations**\n"
                    "└ Manage alliances and settings\n\n"
                    "👥 **Alliance Member Operations**\n"
                    "└ Add, remove, and view members\n\n"
                    "🤖 **Bot Operations**\n"
                    "└ Configure bot settings\n\n"
                    "🎁 **Gift Code Operations**\n"
                    "└ Manage gift codes and rewards\n\n"
                    "📜 **Alliance History**\n"
                    "└ View alliance changes and history\n\n"
                    "🆘 **Support Operations**\n"
                    "└ Access support features\n"
                    "━━━━━━━━━━━━━━━━━━━━━━"
                ),
                color=discord.Color.blue()
            )
            
            view = discord.ui.View()
            view.add_item(discord.ui.Button(
                label="Alliance Operations",
                emoji="🏰",
                style=discord.ButtonStyle.primary,
                custom_id="alliance_operations",
                row=0
            ))
            view.add_item(discord.ui.Button(
                label="Member Operations",
                emoji="👥",
                style=discord.ButtonStyle.primary,
                custom_id="member_operations",
                row=0
            ))
            view.add_item(discord.ui.Button(
                label="Bot Operations",
                emoji="🤖",
                style=discord.ButtonStyle.primary,
                custom_id="bot_operations",
                row=1
            ))
            view.add_item(discord.ui.Button(
                label="Gift Operations",
                emoji="🎁",
                style=discord.ButtonStyle.primary,
                custom_id="gift_code_operations",
                row=1
            ))
            view.add_item(discord.ui.Button(
                label="Alliance History",
                emoji="📜",
                style=discord.ButtonStyle.primary,
                custom_id="alliance_history",
                row=2
            ))
            view.add_item(discord.ui.Button(
                label="Support Operations",
                emoji="🆘",
                style=discord.ButtonStyle.primary,
                custom_id="support_operations",
                row=2
            ))
            view.add_item(discord.ui.Button(
                label="Other Features",
                emoji="🔧",
                style=discord.ButtonStyle.primary,
                custom_id="other_features",
                row=3
            ))

            if admin_count == 0:
                await interaction.edit_original_response(embed=embed, view=view)
            else:
                await interaction.response.send_message(embed=embed, view=view)

        except Exception as e:
            if not any(error_code in str(e) for error_code in ["10062", "40060"]):
                print(f"Settings command error: {e}")
            error_message = "An error occurred while processing your request."
            if not interaction.response.is_done():
                await interaction.response.send_message(error_message, ephemeral=True)
            else:
                await interaction.followup.send(error_message, ephemeral=True)

    @commands.Cog.listener()
    async def on_interaction(self, interaction: discord.Interaction):
        if interaction.type == discord.InteractionType.component:
            custom_id = interaction.data.get("custom_id")
            user_id = interaction.user.id
            user_id = interaction.user.id
            admin = mongo.admin.find_one({"id": user_id})

            if admin is None:
                await interaction.response.send_message("You do not have permission to perform this action.", ephemeral=True)
                return

            try:
                if custom_id == "alliance_operations":
                    embed = discord.Embed(
                        title="🏰 Alliance Operations",
                        description=(
                            "Please select an operation:\n\n"
                            "**Available Operations**\n"
                            "━━━━━━━━━━━━━━━━━━━━━━\n"
                            "➕ **Add Alliance**\n"
                            "└ Create a new alliance\n\n"
                            "✏️ **Edit Alliance**\n"
                            "└ Modify existing alliance settings\n\n"
                            "🗑️ **Delete Alliance**\n"
                            "└ Remove an existing alliance\n\n"
                            "👀 **View Alliances**\n"
                            "└ List all available alliances\n"
                            "━━━━━━━━━━━━━━━━━━━━━━"
                        ),
                        color=discord.Color.blue()
                    )
                    
                    view = discord.ui.View()
                    view.add_item(discord.ui.Button(
                        label="Add Alliance", 
                        emoji="➕",
                        style=discord.ButtonStyle.success, 
                        custom_id="add_alliance", 
                        disabled=admin.get("is_initial", 0) != 1
                    ))
                    view.add_item(discord.ui.Button(
                        label="Edit Alliance", 
                        emoji="✏️",
                        style=discord.ButtonStyle.primary, 
                        custom_id="edit_alliance", 
                        disabled=admin.get("is_initial", 0) != 1
                    ))
                    view.add_item(discord.ui.Button(
                        label="Delete Alliance", 
                        emoji="🗑️",
                        style=discord.ButtonStyle.danger, 
                        custom_id="delete_alliance", 
                        disabled=admin.get("is_initial", 0) != 1
                    ))
                    view.add_item(discord.ui.Button(
                        label="View Alliances", 
                        emoji="👀",
                        style=discord.ButtonStyle.primary, 
                        custom_id="view_alliances"
                    ))
                    view.add_item(discord.ui.Button(
                        label="Check Alliance", 
                        emoji="🔍",
                        style=discord.ButtonStyle.primary, 
                        custom_id="check_alliance"
                    ))
                    view.add_item(discord.ui.Button(
                        label="Main Menu", 
                        emoji="🏠",
                        style=discord.ButtonStyle.secondary, 
                        custom_id="main_menu"
                    ))

                    await interaction.response.edit_message(embed=embed, view=view)

                elif custom_id == "edit_alliance":
                    if admin.get("is_initial", 0) != 1:
                        await interaction.response.send_message("You do not have permission to perform this action.", ephemeral=True)
                        return
                    await self.edit_alliance(interaction)

                elif custom_id == "check_alliance":
                    pipeline = [
                        {"$lookup": {
                            "from": "alliancesettings",
                            "localField": "alliance_id",
                            "foreignField": "alliance_id",
                            "as": "settings"
                        }},
                        {"$unwind": {"path": "$settings", "preserveNullAndEmptyArrays": True}},
                        {"$sort": {"name": 1}},
                        {"$project": {
                            "alliance_id": 1,
                            "name": 1,
                            "interval": {"$ifNull": ["$settings.interval", 0]}
                        }}
                    ]
                    alliances = list(mongo.alliance_list.aggregate(pipeline))

                    if not alliances:
                        await interaction.response.send_message("No alliances found to check.", ephemeral=True)
                        return

                    options = [
                        discord.SelectOption(
                            label="Check All Alliances",
                            value="all",
                            description="Start control process for all alliances",
                            emoji="🔄"
                        )
                    ]
                    
                    options.extend([
                        discord.SelectOption(
                            label=f"{alliance['name'][:40]}",
                            value=str(alliance['alliance_id']),
                            description=f"Control Interval: {alliance['interval']} minutes"
                        ) for alliance in alliances
                    ])

                    select = discord.ui.Select(
                        placeholder="Select an alliance to check",
                        options=options,
                        custom_id="alliance_check_select"
                    )

                    async def alliance_check_callback(select_interaction: discord.Interaction):
                        try:
                            selected_value = select_interaction.data["values"][0]
                            control_cog = self.bot.get_cog('Control')
                            
                            if not control_cog:
                                await select_interaction.response.send_message("Control module not found.", ephemeral=True)
                                return
                            
                            # Ensure the centralized queue processor is running
                            await control_cog.login_handler.start_queue_processor()
                            
                            if selected_value == "all":
                                progress_embed = discord.Embed(
                                    title="🔄 Alliance Control Queue",
                                    description=(
                                        "**Control Queue Information**\n"
                                        "━━━━━━━━━━━━━━━━━━━━━━\n"
                                        f"📊 **Total Alliances:** `{len(alliances)}`\n"
                                        "🔄 **Status:** `Adding alliances to control queue...`\n"
                                        "⏰ **Queue Start:** `Now`\n"
                                        "⚠️ **Note:** `Each alliance will be processed in sequence`\n"
                                        "⏱️ **Wait Time:** `1 minute between each alliance control`\n"
                                        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
                                        "⌛ Please wait while alliances are being processed..."
                                    ),
                                    color=discord.Color.blue()
                                )
                                await select_interaction.response.send_message(embed=progress_embed)
                                msg = await select_interaction.original_response()
                                message_id = msg.id

                                # Queue all alliance operations at once
                                queued_alliances = []
                                for index, alliance in enumerate(alliances):
                                    alliance_id = alliance['alliance_id']
                                    name = alliance['name']
                                    try:
                                        channel_data = mongo.alliancesettings.find_one({"alliance_id": alliance_id})
                                        channel_id = channel_data.get("channel_id") if channel_data else None
                                        channel = self.bot.get_channel(channel_id) if channel_id else select_interaction.channel
                                        
                                        await control_cog.login_handler.queue_operation({
                                            'type': 'alliance_control',
                                            'callback': lambda ch=channel, aid=alliance_id, inter=select_interaction: control_cog.check_agslist(ch, aid, interaction=inter),
                                            'description': f'Manual control check for alliance {name}',
                                            'alliance_id': alliance_id,
                                            'interaction': select_interaction
                                        })
                                        queued_alliances.append((alliance_id, name))
                                    
                                    except Exception as e:
                                        print(f"Error queuing alliance {name}: {e}")
                                        continue
                                
                                # Update status to show all alliances have been queued
                                queue_status_embed = discord.Embed(
                                    title="🔄 Alliance Control Queue",
                                    description=(
                                        "**Control Queue Information**\n"
                                        "━━━━━━━━━━━━━━━━━━━━━━\n"
                                        f"📊 **Total Alliances Queued:** `{len(queued_alliances)}`\n"
                                        f"⏰ **Queue Start:** <t:{int(datetime.now().timestamp())}:R>\n"
                                        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
                                        "⌛ All alliance controls have been queued and will process in order..."
                                    ),
                                    color=discord.Color.blue()
                                )
                                channel = select_interaction.channel
                                msg = await channel.fetch_message(message_id)
                                await msg.edit(embed=queue_status_embed)
                                
                                # Monitor queue completion
                                start_time = datetime.now()
                                while True:
                                    queue_info = control_cog.login_handler.get_queue_info()
                                    
                                    # Check if all our operations are done
                                    if queue_info['queue_size'] == 0 and queue_info['current_operation'] is None:
                                        # Double-check by waiting a moment
                                        await asyncio.sleep(2)
                                        queue_info = control_cog.login_handler.get_queue_info()
                                        if queue_info['queue_size'] == 0 and queue_info['current_operation'] is None:
                                            break
                                    
                                    # Update status periodically
                                    if queue_info['current_operation'] and queue_info['current_operation'].get('type') == 'alliance_control':
                                        current_alliance_id = queue_info['current_operation'].get('alliance_id')
                                        current_name = next((name for aid, name in queued_alliances if aid == current_alliance_id), "Unknown")
                                        
                                        update_embed = discord.Embed(
                                            title="🔄 Alliance Control Queue",
                                            description=(
                                                "**Control Queue Information**\n"
                                                "━━━━━━━━━━━━━━━━━━━━━━\n"
                                                f"📊 **Total Alliances:** `{len(queued_alliances)}`\n"
                                                f"🔄 **Currently Processing:** `{current_name}`\n"
                                                f"📈 **Queue Remaining:** `{queue_info['queue_size']}`\n"
                                                f"⏰ **Started:** <t:{int(start_time.timestamp())}:R>\n"
                                                "━━━━━━━━━━━━━━━━━━━━━━\n\n"
                                                "⌛ Processing controls..."
                                            ),
                                            color=discord.Color.blue()
                                        )
                                        await msg.edit(embed=update_embed)
                                    
                                    await asyncio.sleep(5)  # Check every 5 seconds
                                
                                # All operations complete
                                queue_complete_embed = discord.Embed(
                                    title="✅ Alliance Control Queue Complete",
                                    description=(
                                        "**Queue Status Information**\n"
                                        "━━━━━━━━━━━━━━━━━━━━━━\n"
                                        f"📊 **Total Alliances Processed:** `{len(queued_alliances)}`\n"
                                        "🔄 **Status:** `All controls completed`\n"
                                        f"⏰ **Completion Time:** <t:{int(datetime.now().timestamp())}:R>\n"
                                        f"⏱️ **Total Duration:** `{int((datetime.now() - start_time).total_seconds())} seconds`\n"
                                        "📝 **Note:** `Control results have been shared in respective channels`\n"
                                        "━━━━━━━━━━━━━━━━━━━━━━"
                                    ),
                                    color=discord.Color.green()
                                )
                                await msg.edit(embed=queue_complete_embed)
                            

                            else:
                                alliance_id = int(selected_value)
                                
                                alliance_doc = mongo.alliance_list.find_one({"alliance_id": alliance_id})
                                settings_doc = mongo.alliancesettings.find_one({"alliance_id": alliance_id})
                                
                                if not alliance_doc:
                                    await select_interaction.response.send_message("Alliance not found.", ephemeral=True)
                                    return

                                alliance_name = alliance_doc["name"]
                                channel_id = settings_doc.get("channel_id") if settings_doc else None
                                channel = self.bot.get_channel(channel_id) if channel_id else select_interaction.channel


                                
                                status_embed = discord.Embed(
                                    title="🔍 Alliance Control",
                                    description=(
                                        "**Control Information**\n"
                                        "━━━━━━━━━━━━━━━━━━━━━━\n"
                                        f"📊 **Alliance:** `{alliance_name}`\n"
                                        f"🔄 **Status:** `Queued`\n"
                                        f"⏰ **Queue Time:** `Now`\n"
                                        f"📢 **Results Channel:** `{channel.name if channel else 'Designated channel'}`\n"
                                        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
                                        "⏳ Alliance control will begin shortly..."
                                    ),
                                    color=discord.Color.blue()
                                )
                                await select_interaction.response.send_message(embed=status_embed)
                                
                                await control_cog.login_handler.queue_operation({
                                    'type': 'alliance_control',
                                    'callback': lambda ch=channel, aid=alliance_id: control_cog.check_agslist(ch, aid),
                                    'description': f'Manual control check for alliance {alliance_name}',
                                    'alliance_id': alliance_id
                                })

                        except Exception as e:
                            print(f"Alliance check error: {e}")
                            await select_interaction.response.send_message(
                                "An error occurred during the control process.", 
                                ephemeral=True
                            )

                    select.callback = alliance_check_callback
                    view = discord.ui.View()
                    view.add_item(select)

                    embed = discord.Embed(
                        title="🔍 Alliance Control",
                        description=(
                            "Please select an alliance to check:\n\n"
                            "**Information**\n"
                            "━━━━━━━━━━━━━━━━━━━━━━\n"
                            "• Select 'Check All Alliances' to process all alliances\n"
                            "• Control process may take a few minutes\n"
                            "• Results will be shared in the designated channel\n"
                            "• Other controls will be queued during the process\n"
                            "━━━━━━━━━━━━━━━━━━━━━━"
                        ),
                        color=discord.Color.blue()
                    )
                    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

                elif custom_id == "member_operations":
                    await self.bot.get_cog("AllianceMemberOperations").handle_member_operations(interaction)

                elif custom_id == "bot_operations":
                    try:
                        bot_ops_cog = interaction.client.get_cog("BotOperations")
                        if bot_ops_cog:
                            await bot_ops_cog.show_bot_operations_menu(interaction)
                        else:
                            await interaction.response.send_message(
                                "❌ Bot Operations module not found.",
                                ephemeral=True
                            )
                    except Exception as e:
                        if not any(error_code in str(e) for error_code in ["10062", "40060"]):
                            print(f"Bot operations error: {e}")
                        if not interaction.response.is_done():
                            await interaction.response.send_message(
                                "An error occurred while loading Bot Operations.",
                                ephemeral=True
                            )
                        else:
                            await interaction.followup.send(
                                "An error occurred while loading Bot Operations.",
                                ephemeral=True
                            )

                elif custom_id == "gift_code_operations":
                    try:
                        gift_ops_cog = interaction.client.get_cog("GiftOperations")
                        if gift_ops_cog:
                            await gift_ops_cog.show_gift_menu(interaction)
                        else:
                            await interaction.response.send_message(
                                "❌ Gift Operations module not found.",
                                ephemeral=True
                            )
                    except Exception as e:
                        print(f"Gift operations error: {e}")
                        if not interaction.response.is_done():
                            await interaction.response.send_message(
                                "An error occurred while loading Gift Operations.",
                                ephemeral=True
                            )
                        else:
                            await interaction.followup.send(
                                "An error occurred while loading Gift Operations.",
                                ephemeral=True
                            )

                elif custom_id == "add_alliance":
                    if admin.get("is_initial", 0) != 1:
                        await interaction.response.send_message("You do not have permission to perform this action.", ephemeral=True)
                        return
                    await self.add_alliance(interaction)

                elif custom_id == "delete_alliance":
                    if admin.get("is_initial", 0) != 1:
                        await interaction.response.send_message("You do not have permission to perform this action.", ephemeral=True)
                        return
                    await self.delete_alliance(interaction)

                elif custom_id == "view_alliances":
                    await self.view_alliances(interaction)

                elif custom_id == "support_operations":
                    try:
                        support_ops_cog = interaction.client.get_cog("SupportOperations")
                        if support_ops_cog:
                            await support_ops_cog.show_support_menu(interaction)
                        else:
                            await interaction.response.send_message(
                                "❌ Support Operations module not found.",
                                ephemeral=True
                            )
                    except Exception as e:
                        if not any(error_code in str(e) for error_code in ["10062", "40060"]):
                            print(f"Support operations error: {e}")
                        if not interaction.response.is_done():
                            await interaction.response.send_message(
                                "An error occurred while loading Support Operations.", 
                                ephemeral=True
                            )
                        else:
                            await interaction.followup.send(
                                "An error occurred while loading Support Operations.",
                                ephemeral=True
                            )

                elif custom_id == "alliance_history":
                    try:
                        changes_cog = interaction.client.get_cog("Changes")
                        if changes_cog:
                            await changes_cog.show_alliance_history_menu(interaction)
                        else:
                            await interaction.response.send_message(
                                "❌ Alliance History module not found.",
                                ephemeral=True
                            )
                    except Exception as e:
                        print(f"Alliance history error: {e}")
                        if not interaction.response.is_done():
                            await interaction.response.send_message(
                                "An error occurred while loading Alliance History.",
                                ephemeral=True
                            )
                        else:
                            await interaction.followup.send(
                                "An error occurred while loading Alliance History.",
                                ephemeral=True
                            )

                elif custom_id == "other_features":
                    try:
                        other_features_cog = interaction.client.get_cog("OtherFeatures")
                        if other_features_cog:
                            await other_features_cog.show_other_features_menu(interaction)
                        else:
                            await interaction.response.send_message(
                                "❌ Other Features module not found.",
                                ephemeral=True
                            )
                    except Exception as e:
                        if not any(error_code in str(e) for error_code in ["10062", "40060"]):
                            print(f"Other features error: {e}")
                        if not interaction.response.is_done():
                            await interaction.response.send_message(
                                "An error occurred while loading Other Features menu.",
                                ephemeral=True
                            )
                        else:
                            await interaction.followup.send(
                                "An error occurred while loading Other Features menu.",
                                ephemeral=True
                            )

            except Exception as e:
                if not any(error_code in str(e) for error_code in ["10062", "40060"]):
                    print(f"Error processing interaction with custom_id '{custom_id}': {e}")
                await interaction.response.send_message(
                    "An error occurred while processing your request. Please try again.",
                    ephemeral=True
                )

    async def add_alliance(self, interaction: discord.Interaction):
        if interaction.guild is None:
            await interaction.response.send_message("Please perform this action in a Discord channel.", ephemeral=True)
            return

        modal = AllianceModal(title="Add Alliance")
        await interaction.response.send_modal(modal)
        await modal.wait()

        try:
            alliance_name = modal.name.value.strip()
            interval = int(modal.interval.value.strip())

            embed = discord.Embed(
                title="Channel Selection",
                description=(
                    "**Instructions:**\n"
                    "━━━━━━━━━━━━━━━━━━━━━━\n"
                    "Please select a channel for the alliance\n\n"
                    "**Page:** 1/1\n"
                    f"**Total Channels:** {len(interaction.guild.text_channels)}"
                ),
                color=discord.Color.blue()
            )

            async def channel_select_callback(select_interaction: discord.Interaction):
                try:
                    existing_alliance = mongo.alliance_list.find_one({"name": alliance_name})
                    
                    if existing_alliance:
                        error_embed = discord.Embed(
                            title="Error",
                            description="An alliance with this name already exists.",
                            color=discord.Color.red()
                        )
                        await select_interaction.response.edit_message(embed=error_embed, view=None)
                        return

                    channel_id = int(select_interaction.data["values"][0])

                    # Generate new ID
                    last_alliance = mongo.alliance_list.find_one(sort=[("alliance_id", -1)])
                    alliance_id = (last_alliance["alliance_id"] + 1) if last_alliance else 1

                    mongo.alliance_list.insert_one({
                        "alliance_id": alliance_id,
                        "name": alliance_name,
                        "discord_server_id": interaction.guild.id
                    })
                    
                    mongo.alliancesettings.insert_one({
                        "alliance_id": alliance_id,
                        "channel_id": channel_id,
                        "interval": interval
                    })

                    mongo.giftcodecontrol.insert_one({
                        "alliance_id": alliance_id,
                        "status": 1
                    })

                    result_embed = discord.Embed(
                        title="✅ Alliance Successfully Created",
                        description="The alliance has been created with the following details:",
                        color=discord.Color.green()
                    )
                    
                    info_section = (
                        f"**🛡️ Alliance Name**\n{alliance_name}\n\n"
                        f"**🔢 Alliance ID**\n{alliance_id}\n\n"
                        f"**📢 Channel**\n<#{channel_id}>\n\n"
                        f"**⏱️ Control Interval**\n{interval} minutes"
                    )
                    result_embed.add_field(name="Alliance Details", value=info_section, inline=False)
                    
                    result_embed.set_footer(text="Alliance settings have been successfully saved")
                    result_embed.timestamp = discord.utils.utcnow()
                    
                    await select_interaction.response.edit_message(embed=result_embed, view=None)

                except Exception as e:
                    error_embed = discord.Embed(
                        title="Error",
                        description=f"Error creating alliance: {str(e)}",
                        color=discord.Color.red()
                    )
                    await select_interaction.response.edit_message(embed=error_embed, view=None)

            channels = interaction.guild.text_channels
            view = PaginatedChannelView(channels, channel_select_callback)
            await modal.interaction.response.send_message(embed=embed, view=view, ephemeral=True)

        except ValueError:
            error_embed = discord.Embed(
                title="Error",
                description="Invalid interval value. Please enter a number.",
                color=discord.Color.red()
            )
            await modal.interaction.response.send_message(embed=error_embed, ephemeral=True)
        except Exception as e:
            error_embed = discord.Embed(
                title="Error",
                description=f"Error: {str(e)}",
                color=discord.Color.red()
            )
            await modal.interaction.response.send_message(embed=error_embed, ephemeral=True)

    async def edit_alliance(self, interaction: discord.Interaction):
        pipeline = [
            {"$lookup": {
                "from": "alliancesettings",
                "localField": "alliance_id",
                "foreignField": "alliance_id",
                "as": "settings"
            }},
            {"$unwind": {"path": "$settings", "preserveNullAndEmptyArrays": True}},
            {"$sort": {"name": 1}},
            {"$project": {
                "alliance_id": 1,
                "name": 1,
                "interval": {"$ifNull": ["$settings.interval", 0]}
            }}
        ]
        alliances = list(mongo.alliance_list.aggregate(pipeline))

        if not alliances:
            no_alliance_embed = discord.Embed(
                title="❌ No Alliances Found",
                description="There are no alliances to edit.",
                color=discord.Color.red()
            )
            no_alliance_embed.set_footer(text="Use /alliance create to add a new alliance")
            return await interaction.response.send_message(embed=no_alliance_embed, ephemeral=True)

        alliance_options = [
            discord.SelectOption(
                label=f"{alliance['name']} (ID: {alliance['alliance_id']})",
                value=f"{alliance['alliance_id']}",
                description=f"Interval: {alliance['interval']} minutes"
            ) for alliance in alliances
        ]
        
        items_per_page = 25
        option_pages = [alliance_options[i:i + items_per_page] for i in range(0, len(alliance_options), items_per_page)]
        total_pages = len(option_pages)

        class PaginatedAllianceView(discord.ui.View):
            def __init__(self, pages, original_callback):
                super().__init__(timeout=7200)
                self.current_page = 0
                self.pages = pages
                self.original_callback = original_callback
                self.total_pages = len(pages)
                self.update_view()

            def update_view(self):
                self.clear_items()
                
                select = discord.ui.Select(
                    placeholder=f"Select alliance ({self.current_page + 1}/{self.total_pages})",
                    options=self.pages[self.current_page]
                )
                select.callback = self.original_callback
                self.add_item(select)
                
                previous_button = discord.ui.Button(
                    label="◀️",
                    style=discord.ButtonStyle.grey,
                    custom_id="previous",
                    disabled=(self.current_page == 0)
                )
                previous_button.callback = self.previous_callback
                self.add_item(previous_button)

                next_button = discord.ui.Button(
                    label="▶️",
                    style=discord.ButtonStyle.grey,
                    custom_id="next",
                    disabled=(self.current_page == len(self.pages) - 1)
                )
                next_button.callback = self.next_callback
                self.add_item(next_button)

            async def previous_callback(self, interaction: discord.Interaction):
                self.current_page = (self.current_page - 1) % len(self.pages)
                self.update_view()
                
                embed = interaction.message.embeds[0]
                embed.description = (
                    "**Instructions:**\n"
                    "━━━━━━━━━━━━━━━━━━━━━━\n"
                    "1️⃣ Select an alliance from the dropdown menu\n"
                    "2️⃣ Use ◀️ ▶️ buttons to navigate between pages\n\n"
                    f"**Current Page:** {self.current_page + 1}/{self.total_pages}\n"
                    f"**Total Alliances:** {sum(len(page) for page in self.pages)}\n"
                    "━━━━━━━━━━━━━━━━━━━━━━"
                )
                await interaction.response.edit_message(embed=embed, view=self)

            async def next_callback(self, interaction: discord.Interaction):
                self.current_page = (self.current_page + 1) % len(self.pages)
                self.update_view()
                
                embed = interaction.message.embeds[0]
                embed.description = (
                    "**Instructions:**\n"
                    "━━━━━━━━━━━━━━━━━━━━━━\n"
                    "1️⃣ Select an alliance from the dropdown menu\n"
                    "2️⃣ Use ◀️ ▶️ buttons to navigate between pages\n\n"
                    f"**Current Page:** {self.current_page + 1}/{self.total_pages}\n"
                    f"**Total Alliances:** {sum(len(page) for page in self.pages)}\n"
                    "━━━━━━━━━━━━━━━━━━━━━━"
                )
                await interaction.response.edit_message(embed=embed, view=self)

        async def select_callback(select_interaction: discord.Interaction):
            try:
                alliance_id = int(select_interaction.data["values"][0])
                alliance_data = next(a for a in alliances if a['alliance_id'] == alliance_id)
                
                settings_data = mongo.alliancesettings.find_one({"alliance_id": alliance_id})
                interval = settings_data.get("interval", 0) if settings_data else 0
                current_channel_id = settings_data.get("channel_id") if settings_data else None
                
                modal = AllianceModal(
                    title="Edit Alliance",
                    default_name=alliance_data['name'],
                    default_interval=str(interval)
                )
                await select_interaction.response.send_modal(modal)
                await modal.wait()

                try:
                    alliance_name = modal.name.value.strip()
                    interval = int(modal.interval.value.strip())

                    embed = discord.Embed(
                        title="🔄 Channel Selection",
                        description=(
                            "**Current Channel Information**\n"
                            "━━━━━━━━━━━━━━━━━━━━━━\n"
                            f"📢 Current channel: {f'<#{current_channel_id}>' if current_channel_id else 'Not set'}\n"
                            "**Page:** 1/1\n"
                            f"**Total Channels:** {len(interaction.guild.text_channels)}\n"
                            "━━━━━━━━━━━━━━━━━━━━━━"
                        ),
                        color=discord.Color.blue()
                    )

                    async def channel_select_callback(channel_interaction: discord.Interaction):
                        try:
                            channel_id = int(channel_interaction.data["values"][0])

                            mongo.alliance_list.update_one(
                                {"alliance_id": alliance_id},
                                {"$set": {"name": alliance_name}}
                            )
                            
                            mongo.alliancesettings.update_one(
                                {"alliance_id": alliance_id},
                                {"$set": {"channel_id": channel_id, "interval": interval}},
                                upsert=True
                            )

                            result_embed = discord.Embed(
                                title="✅ Alliance Successfully Updated",
                                description="The alliance details have been updated as follows:",
                                color=discord.Color.green()
                            )
                            
                            info_section = (
                                f"**🛡️ Alliance Name**\n{alliance_name}\n\n"
                                f"**🔢 Alliance ID**\n{alliance_id}\n\n"
                                f"**📢 Channel**\n<#{channel_id}>\n\n"
                                f"**⏱️ Control Interval**\n{interval} minutes"
                            )
                            result_embed.add_field(name="Alliance Details", value=info_section, inline=False)
                            
                            result_embed.set_footer(text="Alliance settings have been successfully saved")
                            result_embed.timestamp = discord.utils.utcnow()
                            
                            await channel_interaction.response.edit_message(embed=result_embed, view=None)

                        except Exception as e:
                            error_embed = discord.Embed(
                                title="❌ Error",
                                description=f"An error occurred while updating the alliance: {str(e)}",
                                color=discord.Color.red()
                            )
                            await channel_interaction.response.edit_message(embed=error_embed, view=None)

                    channels = interaction.guild.text_channels
                    view = PaginatedChannelView(channels, channel_select_callback)
                    await modal.interaction.response.send_message(embed=embed, view=view, ephemeral=True)

                except ValueError:
                    error_embed = discord.Embed(
                        title="Error",
                        description="Invalid interval value. Please enter a number.",
                        color=discord.Color.red()
                    )
                    await modal.interaction.response.send_message(embed=error_embed, ephemeral=True)
                except Exception as e:
                    error_embed = discord.Embed(
                        title="Error",
                        description=f"Error: {str(e)}",
                        color=discord.Color.red()
                    )
                    await modal.interaction.response.send_message(embed=error_embed, ephemeral=True)

            except Exception as e:
                error_embed = discord.Embed(
                    title="❌ Error",
                    description=f"An error occurred: {str(e)}",
                    color=discord.Color.red()
                )
                if not select_interaction.response.is_done():
                    await select_interaction.response.send_message(embed=error_embed, ephemeral=True)
                else:
                    await select_interaction.followup.send(embed=error_embed, ephemeral=True)

        view = PaginatedAllianceView(option_pages, select_callback)
        embed = discord.Embed(
            title="🛡️ Alliance Edit Menu",
            description=(
                "**Instructions:**\n"
                "━━━━━━━━━━━━━━━━━━━━━━\n"
                "1️⃣ Select an alliance from the dropdown menu\n"
                "2️⃣ Use ◀️ ▶️ buttons to navigate between pages\n\n"
                f"**Current Page:** {1}/{total_pages}\n"
                f"**Total Alliances:** {len(alliances)}\n"
                "━━━━━━━━━━━━━━━━━━━━━━"
            ),
            color=discord.Color.blue()
        )
        embed.set_footer(text="Use the dropdown menu below to select an alliance")
        embed.timestamp = discord.utils.utcnow()
        
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    async def delete_alliance(self, interaction: discord.Interaction):
        try:
            alliances = list(mongo.alliance_list.find({}, {"alliance_id": 1, "name": 1}).sort("name", 1))
            
            if not alliances:
                no_alliance_embed = discord.Embed(
                    title="❌ No Alliances Found",
                    description="There are no alliances to delete.",
                    color=discord.Color.red()
                )
                await interaction.response.send_message(embed=no_alliance_embed, ephemeral=True)
                return

            alliance_members = {}
            for alliance in alliances:
                alliance_id = alliance["alliance_id"]
                member_count = mongo.users.count_documents({"alliance": alliance_id})
                alliance_members[alliance_id] = member_count

            items_per_page = 25
            all_options = [
                discord.SelectOption(
                    label=f"{alliance['name'][:40]} (ID: {alliance['alliance_id']})",
                    value=f"{alliance['alliance_id']}",
                    description=f"👥 Members: {alliance_members[alliance['alliance_id']]} | Click to delete",
                    emoji="🗑️"
                ) for alliance in alliances
            ]
            
            option_pages = [all_options[i:i + items_per_page] for i in range(0, len(all_options), items_per_page)]
            
            embed = discord.Embed(
                title="🗑️ Delete Alliance",
                description=(
                    "**⚠️ Warning: This action cannot be undone!**\n"
                    "━━━━━━━━━━━━━━━━━━━━━━\n"
                    "1️⃣ Select an alliance from the dropdown menu\n"
                    "2️⃣ Use ◀️ ▶️ buttons to navigate between pages\n\n"
                    f"**Current Page:** 1/{len(option_pages)}\n"
                    f"**Total Alliances:** {len(alliances)}\n"
                    "━━━━━━━━━━━━━━━━━━━━━━"
                ),
                color=discord.Color.red()
            )
            embed.set_footer(text="⚠️ Warning: Deleting an alliance will remove all its data!")
            embed.timestamp = discord.utils.utcnow()

            view = PaginatedDeleteView(option_pages, self.alliance_delete_callback)
            
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

        except Exception as e:
            print(f"Error in delete_alliance: {e}")
            error_embed = discord.Embed(
                title="❌ Error",
                description="An error occurred while loading the delete menu.",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=error_embed, ephemeral=True)

    async def alliance_delete_callback(self, interaction: discord.Interaction):
        try:
            alliance_id = int(interaction.data["values"][0])
            
            alliance_data = mongo.alliance_list.find_one({"alliance_id": alliance_id})
            
            if not alliance_data:
                await interaction.response.send_message("Alliance not found.", ephemeral=True)
                return
            
            alliance_name = alliance_data["name"]

            settings_count = mongo.alliancesettings.count_documents({"alliance_id": alliance_id})
            users_count = mongo.users.count_documents({"alliance": alliance_id})
            admin_server_count = mongo.adminserver.count_documents({"alliances_id": alliance_id})
            gift_channels_count = mongo.giftcode_channel.count_documents({"alliance_id": alliance_id})
            gift_code_control_count = mongo.giftcodecontrol.count_documents({"alliance_id": alliance_id})

            confirm_embed = discord.Embed(
                title="⚠️ Confirm Alliance Deletion",
                description=(
                    f"Are you sure you want to delete this alliance?\n\n"
                    f"**Alliance Details:**\n"
                    f"🛡️ **Name:** {alliance_name}\n"
                    f"🔢 **ID:** {alliance_id}\n"
                    f"👥 **Members:** {users_count}\n\n"
                    f"**Data to be Deleted:**\n"
                    f"⚙️ Alliance Settings: {settings_count}\n"
                    f"👥 User Records: {users_count}\n"
                    f"🏰 Admin Server Records: {admin_server_count}\n"
                    f"📢 Gift Channels: {gift_channels_count}\n"
                    f"📊 Gift Code Controls: {gift_code_control_count}\n\n"
                    "**⚠️ WARNING: This action cannot be undone!**"
                ),
                color=discord.Color.red()
            )
            
            confirm_view = discord.ui.View(timeout=60)
            
            async def confirm_callback(button_interaction: discord.Interaction):
                try:
                    result = mongo.alliance_list.delete_one({"alliance_id": alliance_id})
                    alliance_count = result.deleted_count
                    
                    result = mongo.alliancesettings.delete_one({"alliance_id": alliance_id})
                    admin_settings_count = result.deleted_count
                    
                    result = mongo.users.delete_many({"alliance": alliance_id})
                    users_count_deleted = result.deleted_count

                    result = mongo.adminserver.delete_many({"alliances_id": alliance_id})
                    admin_server_count = result.deleted_count

                    result = mongo.giftcode_channel.delete_many({"alliance_id": alliance_id})
                    gift_channels_count = result.deleted_count

                    result = mongo.giftcodecontrol.delete_many({"alliance_id": alliance_id})
                    gift_code_control_count = result.deleted_count

                    cleanup_embed = discord.Embed(
                        title="✅ Alliance Successfully Deleted",
                        description=(
                            f"Alliance **{alliance_name}** has been deleted.\n\n"
                            "**Cleaned Up Data:**\n"
                            f"🛡️ Alliance Records: {alliance_count}\n"
                            f"👥 Users Removed: {users_count_deleted}\n"
                            f"⚙️ Alliance Settings: {admin_settings_count}\n"
                            f"🏰 Admin Server Records: {admin_server_count}\n"
                            f"📢 Gift Channels: {gift_channels_count}\n"
                            f"📊 Gift Code Controls: {gift_code_control_count}"
                        ),
                        color=discord.Color.green()
                    )
                    cleanup_embed.set_footer(text="All related data has been successfully removed")
                    cleanup_embed.timestamp = discord.utils.utcnow()
                    
                    await button_interaction.response.edit_message(embed=cleanup_embed, view=None)
                    
                except Exception as e:
                    error_embed = discord.Embed(
                        title="❌ Error",
                        description=f"An error occurred while deleting the alliance: {str(e)}",
                        color=discord.Color.red()
                    )
                    await button_interaction.response.edit_message(embed=error_embed, view=None)

            async def cancel_callback(button_interaction: discord.Interaction):
                cancel_embed = discord.Embed(
                    title="❌ Deletion Cancelled",
                    description="Alliance deletion has been cancelled.",
                    color=discord.Color.grey()
                )
                await button_interaction.response.edit_message(embed=cancel_embed, view=None)

            confirm_button = discord.ui.Button(label="Confirm", style=discord.ButtonStyle.danger)
            cancel_button = discord.ui.Button(label="Cancel", style=discord.ButtonStyle.grey)
            confirm_button.callback = confirm_callback
            cancel_button.callback = cancel_callback
            confirm_view.add_item(confirm_button)
            confirm_view.add_item(cancel_button)

            await interaction.response.edit_message(embed=confirm_embed, view=confirm_view)

        except Exception as e:
            print(f"Error in alliance_delete_callback: {e}")
            error_embed = discord.Embed(
                title="❌ Error",
                description="An error occurred while processing the deletion.",
                color=discord.Color.red()
            )
            if not interaction.response.is_done():
                await interaction.response.send_message(embed=error_embed, ephemeral=True)
            else:
                await interaction.followup.send(embed=error_embed, ephemeral=True)

    async def handle_button_interaction(self, interaction: discord.Interaction):
        custom_id = interaction.data["custom_id"]
        
        if custom_id == "main_menu":
            embed = discord.Embed(
                title="⚙️ Settings Menu",
                description=(
                    "Please select a category:\n\n"
                    "**Menu Categories**\n"
                    "━━━━━━━━━━━━━━━━━━━━━━\n"
                    "🏰 **Alliance Operations**\n"
                    "└ Manage alliances and settings\n\n"
                    "👥 **Alliance Member Operations**\n"
                    "└ Add, remove, and view members\n\n"
                    "🤖 **Bot Operations**\n"
                    "└ Configure bot settings\n\n"
                    "🎁 **Gift Code Operations**\n"
                    "└ Manage gift codes and rewards\n\n"
                    "📜 **Alliance History**\n"
                    "└ View alliance changes and history\n\n"
                    "🆘 **Support Operations**\n"
                    "└ Access support features\n"
                    "━━━━━━━━━━━━━━━━━━━━━━"
                ),
                color=discord.Color.blue()
            )
            
            view = discord.ui.View()
            view.add_item(discord.ui.Button(
                label="Alliance Operations",
                emoji="🏰",
                style=discord.ButtonStyle.primary,
                custom_id="alliance_operations",
                row=0
            ))
            view.add_item(discord.ui.Button(
                label="Member Operations",
                emoji="👥",
                style=discord.ButtonStyle.primary,
                custom_id="member_operations",
                row=0
            ))
            view.add_item(discord.ui.Button(
                label="Bot Operations",
                emoji="🤖",
                style=discord.ButtonStyle.primary,
                custom_id="bot_operations",
                row=1
            ))
            view.add_item(discord.ui.Button(
                label="Gift Operations",
                emoji="🎁",
                style=discord.ButtonStyle.primary,
                custom_id="gift_code_operations",
                row=1
            ))
            view.add_item(discord.ui.Button(
                label="Alliance History",
                emoji="📜",
                style=discord.ButtonStyle.primary,
                custom_id="alliance_history",
                row=2
            ))
            view.add_item(discord.ui.Button(
                label="Support Operations",
                emoji="🆘",
                style=discord.ButtonStyle.primary,
                custom_id="support_operations",
                row=2
            ))
            view.add_item(discord.ui.Button(
                label="Other Features",
                emoji="🔧",
                style=discord.ButtonStyle.primary,
                custom_id="other_features",
                row=3
            ))


            await interaction.response.edit_message(embed=embed, view=view)

        elif custom_id == "other_features":
            try:
                other_features_cog = interaction.client.get_cog("OtherFeatures")
                if other_features_cog:
                    await other_features_cog.show_other_features_menu(interaction)
                else:
                    await interaction.response.send_message(
                        "❌ Other Features module not found.",
                        ephemeral=True
                    )
            except Exception as e:
                if not any(error_code in str(e) for error_code in ["10062", "40060"]):
                    print(f"Other features error: {e}")
                if not interaction.response.is_done():
                    await interaction.response.send_message(
                        "An error occurred while loading Other Features menu.",
                        ephemeral=True
                    )
                else:
                    await interaction.followup.send(
                        "An error occurred while loading Other Features menu.",
                        ephemeral=True
                    )

    async def show_main_menu(self, interaction: discord.Interaction):
        try:
            embed = discord.Embed(
                title="⚙️ Settings Menu",
                description=(
                    "Please select a category:\n\n"
                    "**Menu Categories**\n"
                    "━━━━━━━━━━━━━━━━━━━━━━\n"
                    "🏰 **Alliance Operations**\n"
                    "└ Manage alliances and settings\n\n"
                    "👥 **Alliance Member Operations**\n"
                    "└ Add, remove, and view members\n\n"
                    "🤖 **Bot Operations**\n"
                    "└ Configure bot settings\n\n"
                    "🎁 **Gift Code Operations**\n"
                    "└ Manage gift codes and rewards\n\n"
                    "📜 **Alliance History**\n"
                    "└ View alliance changes and history\n\n"
                    "🆘 **Support Operations**\n"
                    "└ Access support features\n\n"
                    "🔧 **Other Features**\n"
                    "└ Access other features\n"
                    "━━━━━━━━━━━━━━━━━━━━━━"
                ),
                color=discord.Color.blue()
            )
            
            view = discord.ui.View()
            view.add_item(discord.ui.Button(
                label="Alliance Operations",
                emoji="🏰",
                style=discord.ButtonStyle.primary,
                custom_id="alliance_operations",
                row=0
            ))
            view.add_item(discord.ui.Button(
                label="Member Operations",
                emoji="👥",
                style=discord.ButtonStyle.primary,
                custom_id="member_operations",
                row=0
            ))
            view.add_item(discord.ui.Button(
                label="Bot Operations",
                emoji="🤖",
                style=discord.ButtonStyle.primary,
                custom_id="bot_operations",
                row=1
            ))
            view.add_item(discord.ui.Button(
                label="Gift Operations",
                emoji="🎁",
                style=discord.ButtonStyle.primary,
                custom_id="gift_code_operations",
                row=1
            ))
            view.add_item(discord.ui.Button(
                label="Alliance History",
                emoji="📜",
                style=discord.ButtonStyle.primary,
                custom_id="alliance_history",
                row=2
            ))
            view.add_item(discord.ui.Button(
                label="Support Operations",
                emoji="🆘",
                style=discord.ButtonStyle.primary,
                custom_id="support_operations",
                row=2
            ))
            view.add_item(discord.ui.Button(
                label="Other Features",
                emoji="🔧",
                style=discord.ButtonStyle.primary,
                custom_id="other_features",
                row=3
            ))

            try:
                await interaction.response.edit_message(embed=embed, view=view)
            except discord.InteractionResponded:
                pass
                
        except Exception as e:
            pass

    @discord.ui.button(label="Bot Operations", emoji="🤖", style=discord.ButtonStyle.primary, custom_id="bot_operations", row=1)
    async def bot_operations_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            bot_ops_cog = interaction.client.get_cog("BotOperations")
            if bot_ops_cog:
                await bot_ops_cog.show_bot_operations_menu(interaction)
            else:
                await interaction.response.send_message(
                    "❌ Bot Operations module not found.",
                    ephemeral=True
                )
        except Exception as e:
            print(f"Bot operations button error: {e}")
            await interaction.response.send_message(
                "❌ An error occurred. Please try again.",
                ephemeral=True
            )

class AllianceModal(discord.ui.Modal):
    def __init__(self, title: str, default_name: str = "", default_interval: str = "0"):
        super().__init__(title=title)
        
        self.name = discord.ui.TextInput(
            label="Alliance Name",
            placeholder="Enter alliance name",
            default=default_name,
            required=True
        )
        self.add_item(self.name)
        
        self.interval = discord.ui.TextInput(
            label="Control Interval (minutes)",
            placeholder="Enter interval (0 to disable)",
            default=default_interval,
            required=True
        )
        self.add_item(self.interval)

    async def on_submit(self, interaction: discord.Interaction):
        self.interaction = interaction

class AllianceView(discord.ui.View):
    def __init__(self, cog):
        super().__init__()
        self.cog = cog

    @discord.ui.button(
        label="Main Menu",
        emoji="🏠",
        style=discord.ButtonStyle.secondary,
        custom_id="main_menu"
    )
    async def main_menu_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.cog.show_main_menu(interaction)

class MemberOperationsView(discord.ui.View):
    def __init__(self, cog):
        super().__init__(timeout=None)
        self.cog = cog

    async def get_admin_alliances(self, user_id, guild_id):
        self.cog.c_settings.execute("SELECT id, is_initial FROM admin WHERE id = ?", (user_id,))
        admin = self.cog.c_settings.fetchone()
        
        if admin is None:
            return []
            
        is_initial = admin[1]
        
        if is_initial == 1:
            self.cog.c.execute("SELECT alliance_id, name FROM alliance_list ORDER BY name")
        else:
            self.cog.c.execute("""
                SELECT alliance_id, name 
                FROM alliance_list 
                WHERE discord_server_id = ? 
                ORDER BY name
            """, (guild_id,))
            
        return self.cog.c.fetchall()

    @discord.ui.button(label="Add Member", emoji="➕", style=discord.ButtonStyle.primary, custom_id="add_member")
    async def add_member_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            alliances = await self.get_admin_alliances(interaction.user.id, interaction.guild.id)
            if not alliances:
                await interaction.response.send_message("İttifak üyesi ekleme yetkiniz yok.", ephemeral=True)
                return

            options = [
                discord.SelectOption(
                    label=f"{name}",
                    value=str(alliance_id),
                    description=f"İttifak ID: {alliance_id}"
                ) for alliance_id, name in alliances
            ]

            select = discord.ui.Select(
                placeholder="Bir ittifak seçin",
                options=options,
                custom_id="alliance_select"
            )

            view = discord.ui.View()
            view.add_item(select)

            await interaction.response.send_message(
                "Üye eklemek istediğiniz ittifakı seçin:",
                view=view,
                ephemeral=True
            )

        except Exception as e:
            print(f"Error in add_member_button: {e}")
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    "An error occurred during the process of adding a member.",
                    ephemeral=True
                )
            else:
                await interaction.followup.send(
                    "An error occurred during the process of adding a member.",
                    ephemeral=True
                )

    @discord.ui.button(label="Remove Member", emoji="➖", style=discord.ButtonStyle.danger, custom_id="remove_member")
    async def remove_member_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            alliances = await self.get_admin_alliances(interaction.user.id, interaction.guild.id)
            if not alliances:
                await interaction.response.send_message("You are not authorized to delete alliance members.", ephemeral=True)
                return

            options = [
                discord.SelectOption(
                    label=f"{name}",
                    value=str(alliance_id),
                    description=f"Alliance ID: {alliance_id}"
                ) for alliance_id, name in alliances
            ]

            select = discord.ui.Select(
                placeholder="Choose an alliance",
                options=options,
                custom_id="alliance_select_remove"
            )

            view = discord.ui.View()
            view.add_item(select)

            await interaction.response.send_message(
                "Select the alliance you want to delete members from:",
                view=view,
                ephemeral=True
            )

        except Exception as e:
            print(f"Error in remove_member_button: {e}")
            await interaction.response.send_message(
                "An error occurred during the member deletion process.",
                ephemeral=True
            )

    @discord.ui.button(label="View Members", emoji="👥", style=discord.ButtonStyle.primary, custom_id="view_members")
    async def view_members_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            alliances = await self.get_admin_alliances(interaction.user.id, interaction.guild.id)
            if not alliances:
                await interaction.response.send_message("You are not authorized to screen alliance members.", ephemeral=True)
                return

            options = [
                discord.SelectOption(
                    label=f"{name}",
                    value=str(alliance_id),
                    description=f"Alliance ID: {alliance_id}"
                ) for alliance_id, name in alliances
            ]

            select = discord.ui.Select(
                placeholder="Choose an alliance",
                options=options,
                custom_id="alliance_select_view"
            )

            view = discord.ui.View()
            view.add_item(select)

            await interaction.response.send_message(
                "Select the alliance whose members you want to view:",
                view=view,
                ephemeral=True
            )

        except Exception as e:
            print(f"Error in view_members_button: {e}")
            await interaction.response.send_message(
                "An error occurred while viewing the member list.",
                ephemeral=True
            )

    @discord.ui.button(label="Main Menu", emoji="🏠", style=discord.ButtonStyle.secondary, custom_id="main_menu")
    async def main_menu_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            await self.cog.show_main_menu(interaction)
        except Exception as e:
            print(f"Error in main_menu_button: {e}")
            await interaction.response.send_message(
                "An error occurred during return to the main menu.",
                ephemeral=True
            )

class PaginatedDeleteView(discord.ui.View):
    def __init__(self, pages, original_callback):
        super().__init__(timeout=7200)
        self.current_page = 0
        self.pages = pages
        self.original_callback = original_callback
        self.total_pages = len(pages)
        self.update_view()

    def update_view(self):
        self.clear_items()
        
        select = discord.ui.Select(
            placeholder=f"Select alliance to delete ({self.current_page + 1}/{self.total_pages})",
            options=self.pages[self.current_page]
        )
        select.callback = self.original_callback
        self.add_item(select)
        
        previous_button = discord.ui.Button(
            label="◀️",
            style=discord.ButtonStyle.grey,
            custom_id="previous",
            disabled=(self.current_page == 0)
        )
        previous_button.callback = self.previous_callback
        self.add_item(previous_button)

        next_button = discord.ui.Button(
            label="▶️",
            style=discord.ButtonStyle.grey,
            custom_id="next",
            disabled=(self.current_page == len(self.pages) - 1)
        )
        next_button.callback = self.next_callback
        self.add_item(next_button)

    async def previous_callback(self, interaction: discord.Interaction):
        self.current_page = (self.current_page - 1) % len(self.pages)
        self.update_view()
        
        embed = discord.Embed(
            title="🗑️ Delete Alliance",
            description=(
                "**⚠️ Warning: This action cannot be undone!**\n"
                "━━━━━━━━━━━━━━━━━━━━━━\n"
                "1️⃣ Select an alliance from the dropdown menu\n"
                "2️⃣ Use ◀️ ▶️ buttons to navigate between pages\n\n"
                f"**Current Page:** {self.current_page + 1}/{self.total_pages}\n"
                f"**Total Alliances:** {sum(len(page) for page in self.pages)}\n"
                "━━━━━━━━━━━━━━━━━━━━━━"
            ),
            color=discord.Color.red()
        )
        embed.set_footer(text="⚠️ Warning: Deleting an alliance will remove all its data!")
        embed.timestamp = discord.utils.utcnow()
        
        await interaction.response.edit_message(embed=embed, view=self)

    async def next_callback(self, interaction: discord.Interaction):
        self.current_page = (self.current_page + 1) % len(self.pages)
        self.update_view()
        
        embed = discord.Embed(
            title="🗑️ Delete Alliance",
            description=(
                "**⚠️ Warning: This action cannot be undone!**\n"
                "━━━━━━━━━━━━━━━━━━━━━━\n"
                "1️⃣ Select an alliance from the dropdown menu\n"
                "2️⃣ Use ◀️ ▶️ buttons to navigate between pages\n\n"
                f"**Current Page:** {self.current_page + 1}/{self.total_pages}\n"
                f"**Total Alliances:** {sum(len(page) for page in self.pages)}\n"
                "━━━━━━━━━━━━━━━━━━━━━━"
            ),
            color=discord.Color.red()
        )
        embed.set_footer(text="⚠️ Warning: Deleting an alliance will remove all its data!")
        embed.timestamp = discord.utils.utcnow()
        
        await interaction.response.edit_message(embed=embed, view=self)

class PaginatedChannelView(discord.ui.View):
    def __init__(self, channels, original_callback):
        super().__init__(timeout=7200)
        self.current_page = 0
        self.channels = channels
        self.original_callback = original_callback
        self.items_per_page = 25
        self.pages = [channels[i:i + self.items_per_page] for i in range(0, len(channels), self.items_per_page)]
        self.total_pages = len(self.pages)
        self.update_view()

    def update_view(self):
        self.clear_items()
        
        current_channels = self.pages[self.current_page]
        channel_options = [
            discord.SelectOption(
                label=f"#{channel.name}"[:100],
                value=str(channel.id),
                description=f"Channel ID: {channel.id}" if len(f"#{channel.name}") > 40 else None,
                emoji="📢"
            ) for channel in current_channels
        ]
        
        select = discord.ui.Select(
            placeholder=f"Select channel ({self.current_page + 1}/{self.total_pages})",
            options=channel_options
        )
        select.callback = self.original_callback
        self.add_item(select)
        
        if self.total_pages > 1:
            previous_button = discord.ui.Button(
                label="◀️",
                style=discord.ButtonStyle.grey,
                custom_id="previous",
                disabled=(self.current_page == 0)
            )
            previous_button.callback = self.previous_callback
            self.add_item(previous_button)

            next_button = discord.ui.Button(
                label="▶️",
                style=discord.ButtonStyle.grey,
                custom_id="next",
                disabled=(self.current_page == len(self.pages) - 1)
            )
            next_button.callback = self.next_callback
            self.add_item(next_button)

    async def previous_callback(self, interaction: discord.Interaction):
        self.current_page = (self.current_page - 1) % len(self.pages)
        self.update_view()
        
        embed = interaction.message.embeds[0]
        embed.description = (
            f"**Page:** {self.current_page + 1}/{self.total_pages}\n"
            f"**Total Channels:** {len(self.channels)}\n\n"
            "Please select a channel from the menu below."
        )
        
        await interaction.response.edit_message(embed=embed, view=self)

    async def next_callback(self, interaction: discord.Interaction):
        self.current_page = (self.current_page + 1) % len(self.pages)
        self.update_view()
        
        embed = interaction.message.embeds[0]
        embed.description = (
            f"**Page:** {self.current_page + 1}/{self.total_pages}\n"
            f"**Total Channels:** {len(self.channels)}\n\n"
            "Please select a channel from the menu below."
        )
        
        await interaction.response.edit_message(embed=embed, view=self)

async def setup(bot):
    await bot.add_cog(Alliance(bot))
