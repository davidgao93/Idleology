from discord import Message

def load_list(filepath: str) -> list:
    """Load a list from a text file."""
    with open(filepath, "r") as file:
        return [line.strip() for line in file.readlines()]
    
async def clear_msg(message: Message):
    if message:
        await message.delete()