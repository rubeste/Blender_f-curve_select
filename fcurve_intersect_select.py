import bpy
import numpy as np
import logging

bl_info = {
    "name":        "Graph Select Tool",
    "description": "Tool to select an f-curve by box selecting the f-curve itself.",
    "author":      "Ruben van Osch",
    "version":     (0, 3, 0),
    "blender":     (2, 80, 0),
    "location":    "Animation Graph",
    "category":    "Graph",
    "wiki_url":    "https://github.com/rubeste/Blender_f-curve_select",
    "tracker_url": "https://github.com/rubeste/Blender_f-curve_select/issues",
    "warning":     "This version is still in development."
}

log = logging.getLogger(__name__)


class BoxSelectHandlesOperator(bpy.types.Operator):
    """Select F-Curve by intersecting with select box"""
    bl_idname = "graph.select_box_intersect_curve"
    bl_label = "Intersect curve"
    bl_options = {'REGISTER', 'UNDO'}

    # Operator properties
    wait_for_input: bpy.props.BoolProperty(name="Wait for Input", default=True)
    extend: bpy.props.BoolProperty(
        name="Extend", description="Extend the selection", default=False
    )

    # Only show for graph editor
    @classmethod
    def poll(cls, context):
        # Only show if box select works
        return bpy.ops.graph.select_box.poll()

    # Start modal execution
    # Code obtained from Salatfreak at https://github.com/Salatfreak/VSEBoxSelectHandles/blob/master/vse_box_select_handles.py
    def invoke(self, context, event):
        # Get mouse button roles
        keyconfig = context.window_manager.keyconfigs.active
        self._select_mouse = getattr(
            keyconfig.preferences, 'select_mouse', 'LEFT') + 'MOUSE'
        other_mouse = 'RIGHTMOUSE' if self._select_mouse == 'LEFTMOUSE' else 'LEFTMOUSE'

        # Cancel if invoked by wrong mouse button
        if event.type == other_mouse:
            return {'CANCELLED', 'PASS_THROUGH'}

        # Get view
        view = context.area.regions[4].view2d

        # Start with requested state
        if self.wait_for_input:
            self._state = 'WAIT'
        else:
            self._state = 'DRAG'
            if not self.extend:
                bpy.ops.graph.select_all(action='DESELECT')
            self._mouse_start = view.region_to_view(
                event.mouse_region_x, event.mouse_region_y)

        # Start modal execution
        # bpy.ops.sequencer.view_ghost_border(
        #    'INVOKE_DEFAULT', wait_for_input=self.wait_for_input)
        context.window_manager.modal_handler_add(self)
        self._select = True
        return {'RUNNING_MODAL'}

    # Handle modal events
    # Code obtained from Salatfreak at https://github.com/Salatfreak/VSEBoxSelectHandles/blob/master/vse_box_select_handles.py
    def modal(self, context, event):
        # Get view
        view = context.area.regions[4].view2d

        # Get mouse button to handle
        mouse_button = 'LEFTMOUSE' if self.wait_for_input else self._select_mouse

        # Handle inputs
        if self._state in {'FINISHED', 'CANCELLED'}:
            return {self._state}
        if event.type == mouse_button:
            if self._state == 'WAIT' and not event.ctrl:
                if event.value == 'PRESS':
                    if not self.extend:
                        bpy.ops.graph.select_all(action='DESELECT')
                    self._mouse_start = view.region_to_view(
                        event.mouse_region_x, event.mouse_region_y)
                    self._state = 'DRAG'
            if event.value == 'RELEASE':
                if self._state == 'DRAG':
                    self._mouse_end = view.region_to_view(
                        event.mouse_region_x, event.mouse_region_y)
                    if event.shift:
                        self._select = False
                    self.execute(context)
                    self._state = 'FINISHED'
                else:
                    self._state = 'CANCELLED'
        elif event.value == 'PRESS' and event.type in {'RIGHTMOUSE', 'ESC'}:
            self._state = 'CANCELLED'
        return {'PASS_THROUGH'}

    # Main method
    def execute(self, context):
        # Get border
        minValue = min(self._mouse_start[1], self._mouse_end[1])
        maxValue = max(self._mouse_start[1], self._mouse_end[1])
        minFrame = min(self._mouse_start[0], self._mouse_end[0])
        maxFrame = max(self._mouse_start[0], self._mouse_end[0])
        if minValue == maxValue:
            maxValue += 0.1
            minValue -= 0.1
        if minFrame == maxFrame:
            maxFrame += 0.1
            minFrame -= 0.1
        # Remove Hidden curves
        fCurves = self.removeHidden(
            context.object.animation_data.action.fcurves)
        # Get intersected curves
        fCurves = self.getIntersectingCurves(
            context, fCurves, minFrame, maxFrame, minValue, maxValue)
        # Select curves
        self.selectCurves(fCurves)
        return {'FINISHED'}

    # Removes Hidden f-curves
    def removeHidden(self, fCurves):
        result = []
        for f in fCurves:
            if not f.hide:
                result.append(f)
        return result

    # gets all intersecting curves
    def getIntersectingCurves(self, context, fCurves, minFrame, maxFrame, minValue, maxValue):
        result = []
        for f in fCurves:
            if self.doesCurveIntersect(context, minFrame, maxFrame, minValue, maxValue, f):
                result.append(f)
        return result

    def doesCurveIntersect(self, context, minFrame, maxFrame, minValue, maxValue, fCurve):
        i = minFrame
        while i < maxFrame:
            if self.doesValueIntersect(minValue, maxValue, self.calculateValueOfCurve(context, fCurve, i)):
                return True
            i += 0.1
        return False

    # Checks if value intersects
    def doesValueIntersect(self, minValue, maxValue, value):
        if minValue <= value and value <= maxValue:
            return True
        return False

    # Calculates value of curve at frame.
    def calculateValueOfCurve(self, context, fCurve, frame):
        if context.space_data.use_normalization:
            return self.calculateValeOfNormalizedCurve(fCurve, frame)
        return fCurve.evaluate(frame)

    # Gets normalized value of curve with .1 frame interval precision.
    def calculateValeOfNormalizedCurve(self, fCurve, frame):
        value = fCurve.evaluate(frame)
        min = self.calculateMinValue(fCurve)
        max = self.calculateMaxValue(fCurve)
        return ((value-min)/(max-min)*2)-1

    def calculateMaxValue(self, fCurve):
        maxFrame = None
        max = None
        for k in fCurve.keyframe_points:
            if max is None or max < k.co.y:
                maxFrame = k.co.x
                max = k.co.y
        if max < fCurve.evaluate(maxFrame - 0.1):
            i = maxFrame
            while True:
                if max < fCurve.evaluate(i):
                    max = fCurve.evaluate(i)
                elif max >= fCurve.evaluate(i):
                    break
                i -= 0.1
        elif max < fCurve.evaluate(maxFrame + 0.1):
            i = maxFrame
            while True:
                if max < fCurve.evaluate(i):
                    max = fCurve.evaluate(i)
                elif max >= fCurve.evaluate(i):
                    break
                i += 0.1
        return max

    def calculateMinValue(self, fCurve):
        minFrame = None
        min = None
        for k in fCurve.keyframe_points:
            if min is None or min > k.co.y:
                minFrame = k.co.x
                min = k.co.y
        if min > fCurve.evaluate(minFrame - 0.1):
            i = minFrame
            while True:
                if min > fCurve.evaluate(i):
                    min = fCurve.evaluate(i)
                elif min <= fCurve.evaluate(i):
                    break
                i -= 0.1
        elif min > fCurve.evaluate(minFrame + 0.1):
            i = minFrame
            while True:
                if min > fCurve.evaluate(i):
                    min = fCurve.evaluate(i)
                elif min <= fCurve.evaluate(i):
                    break
                i += 0.1
        return min

    # Selects all curves in a collection
    def selectCurves(self, fCurves):
        for f in fCurves:
            f.select = True
            for k in f.keyframe_points:
                k.select_control_point = True
                k.select_left_handle = True
                k.select_right_handle = True
        return


# Register Addon
keymap = None


def register():
    global keymap

    # Register Operator
    bpy.utils.register_class(BoxSelectHandlesOperator)

    # Create keymap for left and right mouse button to be able to react
    # whether the "Select With" preference is set to right or left
    keymap = bpy.context.window_manager.keyconfigs.addon.keymaps.new(
        name='Graph Editor', space_type='GRAPH_EDITOR'
    )
    kmi = keymap.keymap_items.new(
        BoxSelectHandlesOperator.bl_idname, 'LEFTMOUSE', 'PRESS', alt=True
    )
    kmi.properties.wait_for_input = False
    kmi.properties.extend = False
    kmi = keymap.keymap_items.new(
        BoxSelectHandlesOperator.bl_idname, 'RIGHTMOUSE', 'PRESS', alt=True
    )
    kmi.properties.wait_for_input = False
    kmi.properties.extend = False
    kmi = keymap.keymap_items.new(
        BoxSelectHandlesOperator.bl_idname, 'B', 'PRESS', alt=True
    )
    kmi.properties.wait_for_input = True
    kmi.properties.extend = True


def unregister():
    global keymap

    # Remove keymap
    for item in keymap.keymap_items:
        keymap.keymap_items.remove(item)
    keymap = None

    bpy.utils.unregister_class(BoxSelectHandlesOperator)


# Register on script execution
if __name__ == '__main__':
    register()
