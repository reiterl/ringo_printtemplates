from tempfile import NamedTemporaryFile
import logging
from ringo.lib.cache import CACHE_MISC

log = logging.getLogger(__name__)


def setup(config):
    settings = config.registry.settings
    pythonpath = settings.get('converter.python')
    if settings.get('converter.start') == 'true':
        converter = Converter(python=pythonpath)
        converter.start()
        CACHE_MISC.set("converter", converter)

def get_converter():
    return CACHE_MISC.get("converter")

class Converter(object):

    """Converter to convert ODF documents into other formats like pdf,
    xls, doc."""

    def __init__(self, python=None):
        from py3o.renderers.pyuno.main import Convertor
        self._converter = Convertor(python=python)
        self._available = False

    def start(self):
        try:
            self._converter._init_server()
            self._available = True
            log.info("Office Server for document conversation started.")
        except:
            log.exception("Office not started. Converter is not"
                          "available. Forgot to install Libreoffice?")

    def is_available(self):
        return self._available

    def _get_infile(self, data):
        infile = NamedTemporaryFile()
        infile.write(data)
        infile.seek(0)
        return infile

    def convert(self, data, format="ods", update=True):
        """Returns the infile into the given format.

        :data: Loaded data from the source file
        :format: String of the output format
        :returns: Converted data.

        """
        infile = self._get_infile(data)
        outfile = NamedTemporaryFile()
        # Update needs a patch
        #self._converter.convert(infile.name, outfile.name, format, update)
        self._converter.convert(infile.name, outfile.name, format)
        result = outfile.read()
        infile.close()
        outfile.close()
        return result
