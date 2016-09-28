# Define your custom views here or overwrite the default views. Default
# CRUD operations are generated by the ringo frameworkd.
import os
import logging
import StringIO
import mimetypes
from xml.sax.saxutils import escape
from pyramid.view import view_config
from py3o.template import Template
from genshi.core import Markup

from ringo.views.request import (
    handle_params,
    handle_history,
    is_confirmed,
    get_item_from_request,
    get_action_routename
)
from ringo.lib.helpers import get_app_location, prettify
from ringo.views.base import (
    create, rest_create,
    update, rest_update,
    read
)
from ringo.views.base import web_action_view_mapping, rest_action_view_mapping
from ringo_printtemplate.lib.renderer import PrintDialogRenderer
from ringo_printtemplate.odfconv import get_converter
from ringo_printtemplate.model import Printtemplate

log = logging.getLogger(__name__)


class DummyPrintItem(object):

    """Dummy Item used for printing a given set of values in a dictionary"""

    def __init__(self, values):
        """Will convert the given values in the dictionary into
        attributes of the object. Nested dictionarys are currently not
        supported.

        :values: Dict of values.

        """
        self._values = values
        for key in self._values:
            setattr(self, key, self._values[key])

    def __getattr__(self, key):
        if key == 'totuple':
            raise AttributeError()
        return ""


def load_file(data):
    if data.startswith("@"):
        # Load the data from the filesystem.
        # Path is @package:/path/to/file/relative/to/package/file
        app = get_app_location(data.split(":")[0].strip("@"))
        rel_path = data.split(":")[1]
        full_path = os.path.join(app, rel_path)
        with open(full_path, "r") as tf:
            data = tf.read()
    return data


def save_file(request, item):
    """Helper function which is called after the validation of the form
    succeeds. The function will get the data from the file from the
    request and set it in the model including size and mime type.
    Addiotionally it will set the filename based on the uploaded file if
    no other name is given."""
    try:
        #  TODO: Make this method a general helper method in ringo? (ti)
        #  <2015-01-31 12:15>
        # Rewind file
        request.POST.get('file').file.seek(0)
        data = request.POST.get('file').file.read()
        filename = request.POST.get('file').filename
        item.data = data
        item.size = len(data)
        item.mime = mimetypes.guess_type(filename)[0]
        if not request.POST.get('name'):
            item.name = filename
    except AttributeError:
        # Will be raised if the user submits no file.
        pass
    return item


class PrintValueGetter(object):

    def __init__(self, item, request):
        self.item = item
        self.request = request

    def __getattr__(self, name):
        if hasattr(self.item, name):
            value = self.item.get_value(name, expand=True)
            if isinstance(value, basestring):
                value = escape(value)
                value = Markup(value.replace("\n", "<text:line-break/>"))
            return prettify(self.request, value)


def _render_template(request, template, item):
    """Will render the given template with the items data.

    :template: @todo
    :item: @todo
    :returns: @todo

    """
    out = StringIO.StringIO()
    data = load_file(template.data)
    temp = Template(StringIO.StringIO(data), out)
    temp.render({"item": item, "print_item": PrintValueGetter(item, request)})
    return out


def _build_response(request, template, data):
    """Will return a response object with the rendererd template

    :request: Current request
    :template: The template.
    :data: Payload of the response
    :returns: Response object.

    """
    resp = request.response
    resp.content_type = str(mimetypes.guess_type(data.getvalue()))
    resp.content_disposition = 'attachment; filename="%s.odt"' % template.name
    resp.body = data.getvalue()
    return resp


@view_config(route_name=get_action_routename(Printtemplate, 'print'),
             renderer='/default/print.mako')
def generic_print(request):
    data = request.params.mixed()
    template = retrieve_print_template(request, request.matchdict['id'])
    return print_template(request, data, template)


def retrieve_print_template(request, id):
    return request.db.query(Printtemplate).filter(Printtemplate.id == id).one()


def print_template(request, data, template):
    item = DummyPrintItem(data)
    out = _render_template(request, template, item)
    return _build_response(request, template, out)


def print_(request):
    handle_history(request)
    handle_params(request)
    item = get_item_from_request(request)
    renderer = PrintDialogRenderer(request, item)
    form = renderer.form
    if (request.method == 'POST' and
       is_confirmed(request) and
       form.validate(request.params)):
        template = form.data.get('printtemplates')[0]
        # Render the template
        out = _render_template(request, template, item)
        # Build response

        converter = get_converter()
        if converter and converter.is_available():
            out.seek(0)
            out = converter.convert(out.read(), "pdf")
            resp = request.response
            resp.content_type = str(mimetypes.guess_type(out))
            resp.content_disposition = 'attachment; filename="%s.pdf"' \
                                       % template.name
            resp.body = out
            return resp
        return _build_response(request, template, out)
    else:
        clazz = item.__class__
        rvalue = {}
        rvalue['dialog'] = renderer.render()
        rvalue['clazz'] = clazz
        rvalue['item'] = item
        return rvalue


########################################################################
#                     Overrwritten Bassecontroller                     #
########################################################################


def create_(request):
    return create(request, callback=save_file)


def update_(request):
    return update(request, callback=save_file)


def download(request):
    result = read(request)
    item = result['item']
    response = request.response
    response.content_type = str(item.mime)
    response.content_disposition = 'attachment; filename=%s' % item.name
    response.body = load_file(item.data)
    return response


def rest_create_(request):
    return rest_create(request, callback=save_file)


def rest_update_(request):
    return rest_update(request, callback=save_file)

web_action_view_mapping["default"]["print"] = print_
# FIXME: 2015-09-02: Tried to overwrite the routing with view_config but
# without success. So set the views in *_action_view_mapping. I think
# its ok for now but I would prefer using view_config.
web_action_view_mapping["printtemplates"] = {}
web_action_view_mapping["printtemplates"]["create"] = create_
web_action_view_mapping["printtemplates"]["update"] = update_
web_action_view_mapping["printtemplates"]["download"] = download
rest_action_view_mapping["printtemplates"] = {}
rest_action_view_mapping["printtemplates"]["create"] = rest_create_
rest_action_view_mapping["printtemplates"]["update"] = rest_update_
