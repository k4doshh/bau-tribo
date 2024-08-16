import discord
from discord.ext import commands
from discord.ui import Button, View
import json
import asyncio
from datetime import datetime, timezone

# Configuração do bot
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

# Dados de categorias e inventário
categories_items = {}
inventory_data = {}

# Funções de carga e salvamento
def load_categories():
    global categories_items
    try:
        with open('categories.json', 'r') as file:
            categories_items = json.load(file)
    except FileNotFoundError:
        categories_items = {}
    except json.JSONDecodeError:
        categories_items = {}

def save_categories():
    try:
        with open('categories.json', 'w') as file:
            json.dump(categories_items, file, indent=4)
    except Exception as e:
        print(f"Erro ao salvar categorias: {e}")

def load_inventory():
    global inventory_data
    try:
        with open('inventory.json', 'r') as file:
            inventory_data = json.load(file)
    except FileNotFoundError:
        inventory_data = {}

def save_inventory():
    try:
        with open('inventory.json', 'w') as file:
            json.dump(inventory_data, file, indent=4)
    except Exception as e:
        print(f"Erro ao salvar inventário: {e}")

# Carregar dados ao iniciar
load_categories()
load_inventory()

# Função para registrar ações
async def log_action(action, category, item, quantity, channel_id, user):
    channel = bot.get_channel(channel_id)
    if channel:
        now = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')

        full_inventory = ""
        for cat, items in inventory_data.items():
            full_inventory += f"**Categoria:** {cat}\n"
            for item_name, item_quantity in items.items():
                full_inventory += f"  • {item_name}: {item_quantity}\n"
            full_inventory += "\n"

        embed = discord.Embed(
            title="Registro de Ação no Inventário",
            color=discord.Color.blue(),
            timestamp=datetime.now(timezone.utc)
        )
        embed.set_author(name=user.name, icon_url=user.avatar.url)
        embed.add_field(name="Data e Hora", value=now, inline=False)
        embed.add_field(name="Ação", value=action.capitalize(), inline=True)
        embed.add_field(name="Categoria", value=category, inline=True)
        embed.add_field(name="Item", value=item, inline=True)
        embed.add_field(name="Quantidade", value=quantity, inline=True)
        embed.add_field(name="Inventário Atual", value=full_inventory if full_inventory else "Inventário Vazio", inline=False)

        await channel.send(embed=embed)
    else:
        print(f"Erro: Canal com ID {channel_id} não foi encontrado.")

async def clear_channel(channel):
    try:
        await channel.purge()
    except Exception as e:
        print(f"Erro ao limpar o canal: {e}")

# Views e interações

class CategorySelectView(View):
    def __init__(self, action):
        super().__init__(timeout=None)
        self.action = action

        for category in categories_items.keys():
            button = Button(label=category, style=discord.ButtonStyle.primary)

            async def category_callback(interaction: discord.Interaction, category=category):
                items = categories_items[category]
                embed = discord.Embed(
                    title=f"Categoria: {category}",
                    description="Selecione o item abaixo:",
                    color=discord.Color.gold()
                )
                item_view = ItemSelectView(self.action, category, items)
                await interaction.response.send_message(embed=embed, ephemeral=True, view=item_view)
            
            button.callback = category_callback
            self.add_item(button)

class ItemSelectView(View):
    def __init__(self, action, category, items):
        super().__init__(timeout=None)
        self.action = action
        self.category = category

        for item in items:
            button = Button(label=item, style=discord.ButtonStyle.secondary)

            async def item_callback(interaction: discord.Interaction, item=item):
                await interaction.response.send_message(f"Você escolheu o item {item}. Por favor, digite a quantidade no chat.", ephemeral=True)
                
                def check(msg):
                    return msg.author.id == interaction.user.id and msg.channel == interaction.channel
                
                try:
                    msg = await bot.wait_for('message', timeout=60.0, check=check)
                    quantity = int(msg.content)
                except ValueError:
                    await interaction.followup.send("Por favor, insira um número válido para a quantidade.", ephemeral=True)
                    return
                except asyncio.TimeoutError:
                    await interaction.followup.send("Tempo esgotado. Tente novamente.", ephemeral=True)
                    return

                if self.category not in inventory_data:
                    inventory_data[self.category] = {}

                current_quantity = inventory_data[self.category].get(item, 0)

                if self.action == 'remove':
                    if quantity > current_quantity:
                        await interaction.followup.send("Quantidade a ser removida é maior do que a disponível no inventário.", ephemeral=True)
                        return
                    inventory_data[self.category][item] -= quantity
                    if inventory_data[self.category][item] <= 0:
                        del inventory_data[self.category][item]
                elif self.action == 'add':
                    inventory_data[self.category][item] = current_quantity + quantity

                save_inventory()

                if self.action == 'remove':
                    await interaction.followup.send(f"Removido {quantity} de {item} da categoria {self.category}.", ephemeral=True)
                else:
                    await interaction.followup.send(f"Adicionado {quantity} de {item} na categoria {self.category}.", ephemeral=True)

                await log_action(self.action, self.category, item, quantity, 1146625004763619409, interaction.user)

                await clear_channel(interaction.channel)
                await asyncio.sleep(2)
                await interaction.channel.send("Adicione ou remova itens do baú.", view=InventoryView())

            button.callback = item_callback
            self.add_item(button)

class InventoryView(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Adicionar Item", style=discord.ButtonStyle.green)
    async def add_item(self, interaction: discord.Interaction, button: Button):
        embed = discord.Embed(
            title="Adicionar Item",
            description="Selecione uma categoria para adicionar um item:",
            color=discord.Color.green()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True, view=CategorySelectView('add'))

    @discord.ui.button(label="Remover Item", style=discord.ButtonStyle.red)
    async def remove_item(self, interaction: discord.Interaction, button: Button):
        embed = discord.Embed(
            title="Remover Item",
            description="Selecione uma categoria para remover um item:",
            color=discord.Color.red()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True, view=CategorySelectView('remove'))

class ItemModificationView(View):
    def __init__(self, category):
        super().__init__(timeout=None)
        self.category = category

    @discord.ui.button(label="Adicionar Item", style=discord.ButtonStyle.green)
    async def add_item(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_message(f"Digite o nome do item para adicionar à categoria {self.category}:", ephemeral=True)

        def check(msg):
            return msg.author == interaction.user and msg.channel == interaction.channel

        try:
            msg = await bot.wait_for('message', timeout=60.0, check=check)
            item_to_add = msg.content.upper()

            if item_to_add in categories_items[self.category]:
                await interaction.followup.send(f"O item '{item_to_add}' já existe na categoria {self.category}.", ephemeral=True)
            else:
                categories_items[self.category].append(item_to_add)
                save_categories()
                await interaction.followup.send(f"Item '{item_to_add}' foi adicionado com sucesso à categoria {self.category}.", ephemeral=True)
        except asyncio.TimeoutError:
            await interaction.followup.send("Tempo esgotado. Tente novamente.", ephemeral=True)

    @discord.ui.button(label="Remover Item", style=discord.ButtonStyle.red)
    async def remove_item(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_message(f"Digite o nome do item para remover da categoria {self.category}:", ephemeral=True)

        def check(msg):
            return msg.author == interaction.user and msg.channel == interaction.channel

        try:
            msg = await bot.wait_for('message', timeout=60.0, check=check)
            item_to_remove = msg.content.upper()

            if item_to_remove not in categories_items[self.category]:
                await interaction.followup.send(f"O item '{item_to_remove}' não existe na categoria {self.category}.", ephemeral=True)
            else:
                categories_items[self.category].remove(item_to_remove)
                save_categories()
                await interaction.followup.send(f"Item '{item_to_remove}' foi removido da categoria {self.category}.", ephemeral=True)
        except asyncio.TimeoutError:
            await interaction.followup.send("Tempo esgotado. Tente novamente.", ephemeral=True)

class CategoryManageView(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Criar Nova Categoria", style=discord.ButtonStyle.green)
    async def create_category(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_message("Digite o nome da nova categoria:", ephemeral=True)

        def check(msg):
            return msg.author == interaction.user and msg.channel == interaction.channel

        try:
            msg = await bot.wait_for('message', timeout=60.0, check=check)
            new_category = msg.content.upper()

            if new_category in categories_items:
                await interaction.followup.send(f"A categoria '{new_category}' já existe.", ephemeral=True)
            else:
                categories_items[new_category] = []
                save_categories()
                await interaction.followup.send(f"A categoria '{new_category}' foi criada com sucesso!", ephemeral=True)
        except asyncio.TimeoutError:
            await interaction.followup.send("Tempo esgotado. Tente novamente.", ephemeral=True)

    @discord.ui.button(label="Excluir Categoria", style=discord.ButtonStyle.red)
    async def delete_category(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_message("Digite o nome da categoria a ser excluída:", ephemeral=True)

        def check(msg):
            return msg.author == interaction.user and msg.channel == interaction.channel

        try:
            msg = await bot.wait_for('message', timeout=60.0, check=check)
            category_to_delete = msg.content.upper()

            if category_to_delete not in categories_items:
                await interaction.followup.send(f"A categoria '{category_to_delete}' não existe.", ephemeral=True)
            else:
                # Remover a categoria do inventário
                if category_to_delete in inventory_data:
                    del inventory_data[category_to_delete]
                    save_inventory()
                
                # Remover a categoria das categorias
                del categories_items[category_to_delete]
                save_categories()
                await interaction.followup.send(f"A categoria '{category_to_delete}' foi excluída com sucesso!", ephemeral=True)
        except asyncio.TimeoutError:
            await interaction.followup.send("Tempo esgotado. Tente novamente.", ephemeral=True)

    @discord.ui.button(label="Gerenciar Itens em Categoria", style=discord.ButtonStyle.blurple)
    async def manage_items(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_message("Digite o nome da categoria para gerenciar os itens:", ephemeral=True)

        def check(msg):
            return msg.author == interaction.user and msg.channel == interaction.channel

        try:
            msg = await bot.wait_for('message', timeout=60.0, check=check)
            category = msg.content.upper()

            if category not in categories_items:
                await interaction.followup.send(f"A categoria '{category}' não existe.", ephemeral=True)
            else:
                await interaction.followup.send(f"Gerenciando itens na categoria '{category}'", ephemeral=True, view=ItemModificationView(category))
        except asyncio.TimeoutError:
            await interaction.followup.send("Tempo esgotado. Tente novamente.", ephemeral=True)

@bot.command()
async def inventory(ctx):
    """Comando para exibir o inventário e fornecer opções de interação para adicionar ou remover itens."""
    embed = discord.Embed(
        title="Inventário",
        description="Adicione ou remova itens do baú.",
        color=discord.Color.blue()
    )
    await ctx.send(embed=embed, view=InventoryView())

@bot.command()
async def manage_categories(ctx):
    """Comando para gerenciar categorias e itens do inventário."""
    embed = discord.Embed(
        title="Gerenciar Categorias e Itens",
        description="Adicione ou remova categorias e itens do inventário.",
        color=discord.Color.orange()
    )
    await ctx.send(embed=embed, view=CategoryManageView())

@bot.event
async def on_ready():
    print(f'Bot está online como {bot.user.name}')
    channel = bot.get_channel(1146174917964988516)  # Substitua pelo ID do canal de log
    if channel:
        await channel.send("O bot foi reiniciado e está pronto para uso!")
    else:
        print(f'Erro: Canal com ID {1146174917964988516} não foi encontrado.')


bot.run('MTI3MzE5OTEwMzY3NzA0MjcwMA.Ghowdd.U-Fplp1NlLZOzCLENiCH1zpOUBC7QcUfiWKq1M')