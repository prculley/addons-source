# -*- coding: utf-8 -*-
#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2023 Paul Culley
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
#


"Place Enclose tool"

#------------------------------------------------------------------------
#
# standard python modules
#
#------------------------------------------------------------------------

#------------------------------------------------------------------------
#
# GTK/GI modules
#
#------------------------------------------------------------------------
from gi.repository import Gtk

#------------------------------------------------------------------------
#
# GRAMPS modules
#
#------------------------------------------------------------------------
from gramps.gui.plug import tool as Tool
from gramps.gui.display import display_url
from gramps.gui.managedwindow import ManagedWindow
from gramps.gui.utils import ProgressMeter
from gramps.gen.lib import PlaceRef, Place, PlaceName, PlaceType
from gramps.gen.db import DbTxn
from gramps.gen.merge import MergePlaceQuery
from gramps.gen.utils.location import get_location_list

from gramps.gui.dialog import OkDialog, WarningDialog, ErrorDialog
from gramps.gen.display.place import displayer as _pdx
_pd = _pdx.display
from gramps.gen.const import GRAMPS_LOCALE as glocale
try:
    _trans = glocale.get_addon_translator(__file__)
except ValueError:
    _trans = glocale.translation
_ = _trans.gettext


TITLE = _("Place Enclosure")
TYPES = {
    "USA" : [PlaceType.COUNTRY, PlaceType.STATE, PlaceType.COUNTY,
             PlaceType.CITY, PlaceType.STREET],
    "Canada" : [PlaceType.COUNTRY, PlaceType.PROVINCE, PlaceType.COUNTY,
             PlaceType.CITY, PlaceType.STREET]}
#------------------------------------------------------------------------
#
#
#
#------------------------------------------------------------------------
class PlaceEnclose(Tool.Tool, ManagedWindow):

    def __init__(self, dbstate, user, options_class, name, callback=None):

        self.options = PlaceEncloseOptions('pluginmanager')
        Tool.Tool.__init__(self, dbstate, options_class, name)
        self.db = dbstate.db
        self.dbstate = dbstate
        self.active_name = TITLE
        ManagedWindow.__init__(self, user.uistate, [], self.__class__)

        self.window = Gtk.Window()
        self.window.set_size_request(740, 500)
        self.window.set_position(Gtk.WindowPosition.CENTER_ON_PARENT)
        self.set_window(self.window, None, TITLE, None)
        # main area
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.window.add(vbox)
        scrolled_window = Gtk.ScrolledWindow(expand=True)
        info_text_view = Gtk.TextView()
        scrolled_window.add(info_text_view)
        self.info_text_buf = info_text_view.get_buffer()
        vbox.add(scrolled_window)
        bbox = Gtk.ButtonBox(orientation=Gtk.Orientation.HORIZONTAL)
        vbox.pack_start(bbox, False, False, 5)
        # Help
        help_btn = Gtk.Button(label=_('Help'))
        help_btn.connect('clicked', self.on_help_clicked)
        bbox.add(help_btn)
        # Combo
        close_btn = Gtk.Button(label=_('Close'))
        close_btn.set_tooltip_text(_('Close the Type Cleanup Tool'))
        close_btn.connect('clicked', self.close)
        bbox.add(close_btn)
        self.show()
        self.run_tool()

    def build_menu_names(self, _obj):
        return (self.active_name, TITLE)

    def on_help_clicked(self, dummy):
        """ Button: Display the relevant portion of GRAMPS manual"""
        display_url(
            'http://www.gramps-project.org/wiki/index.php?title=Place_Enclose_tool')

    def showline(self, status, placename):
        _iter = self.info_text_buf.get_end_iter()
        self.info_text_buf.insert(_iter, "{0}:  {1}\n".format(status, placename, -1))

    def run_tool(self):
        self.pnames = {}
        progress = ProgressMeter(_("Scanning and Enclosing Places"),'')
        pcount = self.db.get_number_of_places()

        progress.set_pass(_('Scanning Places, step 1'), pcount)

        merges = []
        for pl1 in self.db.iter_places():
            place_title = _pd(self.db, pl1, fmt=0)
            pl2_hnd = self.pnames.get(place_title, None)
            if pl2_hnd:
                # we have a duplicate, we want to merge.
                self.showline(_("Duplicated"), place_title)
                merges.append((pl1, pl2_hnd))
            self.pnames[place_title] = pl1.handle
            progress.step()
        if merges:
            progress.set_pass(_('Merging Places, step 2'), len(merges))
        for pl1, pl2_hnd in merges:
            pl2 = self.db.get_place_from_handle(pl2_hnd)
            if pl2.lat:
                pl1.lat = pl2.lat
                pl1.long = pl2.long
            if pl2.code:
                pl1.code = pl2.code
            if pl2.place_type != PlaceType.UNKNOWN:
                pl1.place_type = pl2.place_type
            if pl2.name.lang or not pl2.name.date.is_empty():
                pl1.name = pl2.name
            query = MergePlaceQuery(self.dbstate, pl1, pl2)
            query.execute()
#        return

        progress.set_pass(_('Enclosing Places, step 3'), pcount)
        with DbTxn(_("Enclose Tool"), self.db, batch=True) as trans:
            for place in self.db.iter_places():
                if place.place_type == _('Address'):
                    continue
                progress.step()
                self.process_place(place, trans)

        progress.set_pass(_('Fixing Place Types, step 4'), pcount)
        with DbTxn(_("Enclose Tool"), self.db, batch=True) as trans:
            for place in self.db.iter_places():
                if place.place_type == _('Address'):
                    continue
                progress.step()
                self.process_place_types(place, trans)
        progress.close()

    def process_place(self, place, trans):
        # deal with one input place
        update = False
        while True:  # loop over name until all ', ' are done
            pname = place.name.get_value()
            splits = pname.rsplit(', ', maxsplit=1)
            place.name.set_value(splits[0])  # save front part of name
            if len(splits) == 1:
                # no comma, nothing to do
                if update:
                    self.db.commit_place(place, trans)
                    self.showline(_("Updated"), place.title)
                break
            # we have a back half of the name
            update = True
            sp_name = splits[1]
            # see if we need to append any current enclosing places
            enc_places = place.get_placeref_list()
            if enc_places:
                # enclosing place, assume only one
                enc_place = self.db.get_place_from_handle(enc_places[0].ref)
                enc_pname = _pd(self.db, enc_place, fmt=0)
                sp_name += ', ' + enc_pname
            if sp_name in self.pnames:
                # we already have the split name in db so set it to enclose
                encl_place_hnd = self.pnames[sp_name]
            else:
                # we need to make the sp_name into a new enclosing place
                enc_place = Place()
                enc_place.name.set_value(splits[1])  # save new name
                enc_place.title = sp_name
                if enc_places:
                    # place under analysis was already enclosed
                    enc_place.set_placeref_list(enc_places)  # so new on gets same
                encl_place_hnd = self.db.add_place(enc_place, trans)
                self.showline(_("New Place"), sp_name)
                self.pnames[sp_name] = encl_place_hnd  # add it to our places dict
            # we need to update place under analysis with new enclosing PlaceRef
            pref = PlaceRef()
            pref.set_reference_handle(encl_place_hnd)
            placerefs = []
            placerefs.append(pref)
            place.set_placeref_list(placerefs)

    def process_place_types(self, place, trans):
        # deal with one input place
        visited = [place.handle]
        # get list of enclosing places
        lines = [(place.name.get_value(), place, place.get_type())]
        while True:
            handle = None
            pr_list = place.get_placeref_list()
            if pr_list:
                # we assume simple enclosure (could be an issue with dated or lang
                # on an enclosing place)
                handle = pr_list[0].ref
            if handle is None or handle in visited:
                break
            place = self.db.get_place_from_handle(handle)
            visited.append(handle)
            # Again, we assume that the place name is good one
            lines.append((place.name.get_value(), place, place.get_type()))

        length = len(lines)
        index = 0
        # Only want to process longer enclosures where we are more confident of typing
        if length == 5 or length == 4:
            for line in reversed(lines):
                if not index:
                    types = TYPES.get(line[0], None)  # should be country
                    if not types:
                        return
                if line[2] == PlaceType.UNKNOWN:
                    # we can add a PlaceType
                    plc = line[1]
                    if contains_digit(line[0]) and types[index] == PlaceType.CITY:
                        plc.set_type(PlaceType.LOCALITY)
                    else:
                        plc.set_type(types[index])
                    self.db.commit_place(plc, trans)
                    self.showline(_("Type added"), _pd(self.db, plc, fmt=0))
                index += 1

    def on_apply_clicked(self,obj):
        '''execute all the actions in the treeview
        '''
        #OkDialog(_('Change places'),msg,self.window)


#------------------------------------------------------------------------
#
#
#
#------------------------------------------------------------------------
class PlaceEncloseOptions(Tool.ToolOptions):
    """
    Defines options and provides handling interface.
    """

    def __init__(self,name,person_id=None):
        Tool.ToolOptions.__init__(self,name,person_id)
        #self.set_new_options()


    def set_new_options(self):
        # Options specific for this report
        self.options_dict = {
            'filternumber' : 0,
        }
        self.options_help = {
            'filternumber' : ("=int", "integer indicating which place filter to"
                                    "use",  "integer"),
        }

def contains_digit(string):
    return any(i.isdigit() for i in string)
