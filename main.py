# region setup required library
from setuplibrary import SetupLibrary as pre

pre.setup()
# endregion

# region load constant
from utils.constant import Constant as const

const.load_configuration()
# endregion

# region run client
from client import Client

client = Client()
client.run()
# endregion