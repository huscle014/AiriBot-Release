import gettext

class Translator():

    __slots__ = ('translator')

    def __init__(self, locale):
        self.translator = self.get_translator(locale)

    def get_translator(self, locale):
        # Return a translator object for the specified locale
        return gettext.translation('airibot', localedir='locales', languages=[locale])

    def translate(self, message):
        # Translate the message using the provided translator
        return self.translator.gettext(message)