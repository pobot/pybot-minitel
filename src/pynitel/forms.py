# -*- coding: utf-8 -*-

""" A simple Minitel forms management toolkit.
"""

from collections import namedtuple
import json

from .core import Minitel
from .constants import *

__author__ = 'Eric Pascual'


class Form(object):
    """ Defines the forms in terms of layout and field connection with the application.

    A form is made of static prompts and entry fields. The class handles its rendering
    and the management of user interactions when modifying its content.

    The definition of the form can be provided by calls to :py:meth:`add_prompt` and
    :py:meth:`add_field`. This can also be done by loading the equivalent JSON data
    structure, using :py:meth:`load_definition`.

    For convenience, the :py:meth:`dump_definition` does the reverse operation, which
    allows producing the JSON data directly from the current definition of the form.
    """
    def __init__(self, mt):
        """
        :param Minitel mt: the Minitel instance
        """
        if not (mt and isinstance(mt, Minitel)):
            raise ValueError('missing or invalid mt parameter')

        self._mt = mt
        self._width = 80 if mt.is_w80() else 40

        self._prompts = []
        self._fields = {}
        self._fields_sequence = []
        self._prepared = False

    def add_prompt(self, x, y, text):
        """ Adds a fixed text to the form, at a given position.

        :param int x: X coordinate of the prompt start position
        :param int y: Y coordinate of the prompt start position
        :param str text: the prompt text (can include an attributes sequence)
        """
        self._prompts.append(PromptDefinition(x, y, text))
        self._prepared = False

    def add_field(self, name, x, y, size, marker='.'):
        """ Adds a field to the form, at a given position and with a given size.

        :param str name: the field name
        :param int x: X coordinate of the prompt start position
        :param int y: Y coordinate of the prompt start position
        :param int size: the field size
        :param char marker: the character used to mark the fields area (default: '.')
        """
        self._fields[name] = FieldDefinition(x, y, size, marker or '.')
        self._prepared = False

    def _screen_pos(self, o):
        return o.y * self._width + o.x

    def _cmp_prompt(self, a, b):
        return cmp(self._screen_pos(a), self._screen_pos(b))

    def _cmp_field(self, a, b):
        return cmp(self._screen_pos(self._fields[a]), self._screen_pos(self._fields[b]))

    def prepare(self):
        """ Prepares the form by sorting the prompts and fields according to
         their position.

         Is automatically invoked by :py:meth:`render`.
        """
        if self._prepared:
            return

        self._prompts.sort(self._cmp_prompt)
        self._fields_sequence = (sorted(self._fields.keys(), cmp=self._cmp_field))

        self._prepared = True

    def render(self, content=None):
        """ Renders the form on the screen.

        Should normally be invoked before calling :py:meth:`input`.

        :param dict content: optional dictionary containing the initial field values
        """
        content = content or {}

        self.prepare()
        self._mt.clear_screen()
        for prompt in self._prompts:
            self._mt.display_text(prompt.text, prompt.x, prompt.y)

        for field_name in self._fields_sequence:
            field = self._fields[field_name]
            value = content.get(field_name, '')
            self._mt.display_text(value.ljust(field.size, field.marker), field.x, field.y)

    def input(self, content=None):
        """ Handles user interactions and return the fields content if submitted.

        The form is submitted when the 'ENVOI' (SEND) key is hit. It is canceled when hitting the
        'SOMMAIRE' (CONTENT) key.

        :param dict content: optional dictionary containing the initial field values
        :return: the fields content if the form has been submitted, None otherwise.
        :rtype: dict
        """
        content = content or {}

        field_num = 0
        field_count = len(self._fields_sequence)
        self._mt.show_cursor()
        try:
            while True:
                field_name = self._fields_sequence[field_num]
                field = self._fields[field_name]
                value, key = self._mt.rlinput(field.size, field.marker, (field.x, field.y), content.get(field_name, ''))
                if key == KeyCode.CONTENT:
                    return None

                content[field_name] = value
                if key == KeyCode.SEND:
                    return content

                if key in (KeyCode.NEXT, CR):
                    field_num = (field_num + 1) % field_count
                elif key == KeyCode.PREV:
                    field_num = (field_num - 1) % field_count
                else:
                    self._mt.beep()

        finally:
            self._mt.show_cursor(False)

    def render_and_input(self, content=None):
        """ A shortcut for the render / input sequence.

        Refer to :py:meth:`render` and :py:meth:`input` for documentation of the parameters
        and return value.
        """
        self.render(content)
        return self.input(content)

    def load_definition(self, data):
        """ Loads the form definition from the provided JSON structure.

        Refer to :py:meth:`dump_definition` documentation for the structure
        specifications.

        :param str data: the form definition in JSON format
        :raise ValueError: if no data or invalid JSON data provided
        """
        if not data:
            raise ValueError('no definition provided')

        try:
            defs = json.loads(data)
            self._fields = {}
            self._prompts = []

            for prompt_def in defs['prompts']:
                x, y, text = prompt_def
                self.add_prompt(int(x), int(y), str(text))

            for field_name, field_def in defs['fields'].iteritems():
                x, y, size, marker = (field_def + ['.'])[:4]

                self.add_field(str(field_name), int(x), int(y), int(size), str(marker))

        except ValueError as e:
            raise ValueError('invalid form definition data (%s)' % e)

    def dump_definition(self):
        """ Returns the form current definition as a JSON formatted structure.

        The structure is a dictionary such as : ::

            {
                "prompts": [
                    [0, 2, "First name"],
                    [0, 4, "Last name"],
                    [30, 23, "ENVOI"]
                ],
                "fields": {
                    "lname": [15, 4, 20, "."],
                    "fname": [15, 2, 20, "."]
                }
            }

        The prompt definitions are tuples, containing in sequence :

            - the X position
            - the Y position
            - the text

        The field definitions are tuples, containing in sequence :

            - the X position
            - the Y position
            - the size (in characters)
            - the marker character (defaulted to ``.`` if not included)

        They are packed in a dictionary keyed by the field name.

        :return: JSON form definition
        :rtype: str
        """
        data = {
            'prompts': self._prompts,
            'fields': self._fields
        }
        return json.dumps(data)


PromptDefinition = namedtuple('PromptDefinition', 'x y text')


class FieldDefinition(namedtuple('FieldDefinition', 'x y size marker')):
    __slots__ = ()

    def __new__(cls, x, y, size, marker='.'):
        if not 0 <= x < 40:
            raise ValueError('invalid x position : %s' % x)
        if not 0 <= y < 23:
            raise ValueError('invalid y position : %s' % y)
        if not 0 <= size < 40:
            raise ValueError('invalid field size : %s' % size)

        return super(FieldDefinition, cls).__new__(cls, x, y, size, (marker or '.')[0])