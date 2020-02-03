#!/usr/bin/python

# PCBmodE, a printed circuit design software with a twist
# Copyright (C) 2020 Saar Drimer
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.


import copy

from pcbmode.config import config
from pcbmode.utils import messages as msg
from pcbmode.utils import svg
from pcbmode.utils import utils
from pcbmode.utils import place
from pcbmode.utils.style import Style
from pcbmode.utils.point import Point
from pcbmode.utils.shape import Shape


class Footprint:
    """
    """

    def __init__(self, footprint):

        self._footprint = footprint

        # This is where the shapes for placement are stored, by layer
        self._shapes = {
            "conductor": {},
            "pours": {},
            "soldermask": {},
            "silkscreen": {},
            "assembly": {},
            "solderpaste": {},
            "drills": {},
        }

        self._process_pins()
        self._process_pours()
        self._process_shapes()
        self._process_assembly_shapes()

    def get_shapes(self):
        return self._shapes

    def _process_pins(self):
        """
        Converts pins into 'shapes'
        """

        pins_dict = self._footprint.get("pins", {})
        pads_dict = self._footprint.get("pads", {})

        for pin_name in pins_dict:

            pin_dict = pins_dict[pin_name]["layout"]
            pin_loc_p = Point(pin_dict.get("location", [0, 0]))
            pad_name = pin_dict["pad"]
            pad_dict = pads_dict[pad_name]
            pin_rotate = pin_dict.get("rotate", 0)
            shapes = pad_dict.get("shapes", [])

            for shape_dict in shapes:

                # Which layer(s) to place the shape on
                layers = utils.getExtendedLayerList(shape_dict.get("layers", ["top"]))

                # Add the pin's location to the pad's location
                shape_loc = shape_dict.get("location", [0,0])

                # TODO: NASTY hack, but can't continue without it for now
                if isinstance(shape_loc, Point) is True:
                    shape_loc_p = shape_loc
                else:
                    shape_loc_p = Point(shape_loc)

                shape_dict["location"] = pin_loc_p + shape_loc_p

                # Add the pin's rotation to the pad's rotation
                shape_dict["rotate"] = (shape_dict.get("rotate", 0)) + pin_rotate

                for layer in layers:

                    pad_shape = Shape(shape_dict)

                    # Add the label to the shape instance and not to the dict so
                    # theat is doesn't propegate to the other derived shapes later on
                    if pin_dict.get("show-label", True) is True:
                        # Use 'label' or default to the pin name
                        pad_shape.set_label(pin_dict.get("label", pin_name))
                        pad_shape.set_label_style_class("pad-labels")

                    # Add the exact shape to the conductor layer shapes
                    if layer in self._shapes["conductor"]:
                        self._shapes["conductor"][layer].append(pad_shape)
                    else:
                        self._shapes["conductor"][layer] = [pad_shape]

                    for sheet in ["soldermask", "solderpaste"]:

                        # Get a custom shape specification if it exists
                        sdict_list = shape_dict.get(sheet, None)

                        # Not defined; default
                        if sdict_list == None:
                            # Use default settings for shape based on the pad shape
                            sdict = shape_dict.copy()

                            # Which shape type is the pad?
                            shape_type = pad_shape.get_type()

                            cfg_def = config.cfg["distances"][sheet]

                            # Apply modifier based on shape type
                            if shape_type == "path":
                                sdict["scale"] = (
                                    pad_shape.getScale() * cfg_def["path-scale"]
                                )
                            elif shape_type == "rect":
                                sdict["width"] += cfg_def["rect-buffer"]
                                sdict["height"] += cfg_def["rect-buffer"]
                            elif shape_type == "circle":
                                sdict["diameter"] += cfg_def["circle-buffer"]
                            else:
                                pass

                            # Create shape based on new dictionary
                            sshape = Shape(sdict)

                            # Add shape to footprint's shape dictionary
                            if layer in self._shapes[sheet]:
                                self._shapes[sheet][layer].append(sshape)
                            else:
                                self._shapes[sheet][layer] = [sshape]

                        # Do not place shape
                        elif (sdict_list == {}) or (sdict_list == []):
                            pass

                        # Custom shape definition
                        else:

                            # If dict (as before support of multiple
                            # shapes) then append to a single element
                            # list
                            if type(sdict_list) is dict:
                                sdict_list = [sdict_list]

                            # Process list of shapes
                            for sdict_ in sdict_list:
                                sdict = sdict_.copy()
                                shape_loc = Point(sdict.get("location", [0, 0]))

                                # Apply rotation
                                sdict["rotate"] = (sdict.get("rotate", 0)) + pin_rotate

                                # Rotate location
                                shape_loc.rotate(pin_rotate)

                                sdict["location"] = shape_loc_p + pin_loc_p

                                # Create new shape
                                sshape = Shape(sdict)

                                # Add shape to footprint's shape dictionary
                                # self._shapes[stype][layer].append(sshape)
                                if layer in self._shapes[sheet]:
                                    self._shapes[sheet][layer].append(sshape)
                                else:
                                    self._shapes[sheet][layer] = [sshape]

            drills = pad_dict.get("drills", [])
            for drill_dict in drills:
                drill_dict = drill_dict.copy()
                drill_dict["type"] = drill_dict.get("type") or "drill"
                drill_loc_p = Point(drill_dict.get("location", [0, 0]))
                drill_dict["location"] = drill_loc_p + pin_loc_p
                shape = Shape(drill_dict)

                if "top" in self._shapes["drills"]:
                    self._shapes["drills"]["top"].append(shape)
                else:
                    self._shapes["drills"]["top"] = [shape]

    def _process_pours(self):
        """
        """

        try:
            shapes = self._footprint["layout"]["pours"]["shapes"]
        except:
            return

        for shape_dict in shapes:
            layers = utils.getExtendedLayerList(shape_dict.get("layers") or ["top"])
            for layer in layers:
                shape = Shape(shape_dict)

                if layer in self._shapes["pours"]:
                    self._shapes["pours"][layer].append(shape)
                else:
                    self._shapes["pours"][layer] = [shape]

    def _process_shapes(self):
        """
        """

        sheets = ["conductor", "silkscreen", "soldermask"]

        for sheet in sheets:

            try:
                shapes = self._footprint["layout"][sheet]["shapes"] or []
            except:
                shapes = []

            for shape_dict in shapes:
                layers = utils.getExtendedLayerList(shape_dict.get("layers") or ["top"])
                for layer in layers:
                    # Mirror the shape if it's text and on bottom later,
                    # but let explicit shape setting override
                    if layer == "bottom":
                        if shape_dict["type"] == "text":
                            shape_dict["mirror"] = shape_dict.get("mirror") or "True"
                    shape = Shape(shape_dict)

                    if layer in self._shapes[sheet]:
                        self._shapes[sheet][layer].append(shape)
                    else:
                        self._shapes[sheet][layer] = [shape]

    def _process_assembly_shapes(self):
        """
        """
        try:
            shapes = self._footprint["layout"]["assembly"]["shapes"]
        except:
            return

        for shape_dict in shapes:
            layers = utils.getExtendedLayerList(shape_dict.get("layer") or ["top"])
            for layer in layers:
                shape = Shape(shape_dict)

                if layer in self._shapes["assembly"]:
                    self._shapes["assembly"][layer].append(shape)
                else:
                    self._shapes["assembly"][layer] = [shape]
