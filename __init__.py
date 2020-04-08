bl_info = {
    "name": "Render Burst",
    "category": "Render",
    "blender": (2, 80, 0),
    "author" : "Aidy Burrows, Gleb Alexandrov, Roman Alexandrov, CreativeShrimp.com <support@creativeshrimp.com>",
    "version" : (1, 1, 29),
    "description" :
            "Render all cameras, one by one, and store results.",
}

import bpy
import os

def ShowMessageBox(message = "", title = "Message Box", icon = 'INFO'):

    def draw(self, context):
        self.layout.label(text=message)

    bpy.context.window_manager.popup_menu(draw, title = title, icon = icon)

class RenderingHelpers():
    # This class contains all functionality previously used in RenderBurst(bpy.types.Operator) so it can be reused.
    # shots = None

    @staticmethod
    def imagesToRender(onlySelected = False):
        '''
        Define the images/shots to render. Will get all visible cameras unless onlySelected = True.
        '''
        shots = None
        if onlySelected:
            shots = [ o.name+'' for o in bpy.context.selected_objects if o.type=='CAMERA' and o.visible_get() == True]
        else:
            shots = [ o.name+'' for o in bpy.context.visible_objects if o.type=='CAMERA' and o.visible_get() == True ]

        return shots

    @staticmethod
    def renderPath(localPath, filePath, newFileName, fileExtension):
        '''
        Calculates the render path based on the parameters.
        '''
        is_relative_path = True

        if filePath != "":
            if filePath[0]+filePath[1] == "//":
                is_relative_path = True
                filePath = bpy.path.abspath(filePath)
            else:
                is_relative_path = False

            localPath = os.path.dirname(filePath)

            if is_relative_path:
                localPath = bpy.path.relpath(localPath)

            localPath = localPath.rstrip("/")
            localPath = localPath.rstrip("\\")
            if localPath=="":
                localPath="/" 
            localPath+="/"

        return localPath + newFileName + fileExtension

class RenderBurst(bpy.types.Operator):
    """Render all cameras"""
    bl_idname = "render.renderburst"
    bl_label = "Render Burst"

    # Define some variables to register
    _timer = None
    shots = None
    stop = None
    rendering = None
    path = "//"
    disablerbbutton = False

    def pre(self, dummy, thrd = None):
        self.rendering = True

    def post(self, dummy, thrd = None):
        # This is just to render the next image in another path
        self.shots.pop(0) 
        self.rendering = False

    def cancelled(self, dummy, thrd = None):
        self.stop = True

    def execute(self, context):
        # Define the variables during execution. This allows
        # to define when called from a button
        self.stop = False
        self.rendering = False
        scene = bpy.context.scene
        wm = bpy.context.window_manager
        # Define the images/shots to render
        self.shots = RenderingHelpers.imagesToRender(onlySelected = wm.rb_filter.rb_filter_enum == 'selected')
        
        if len(self.shots) < 0:
            self.report({"WARNING"}, 'No cameras defined')
            return {"FINISHED"}        

        bpy.app.handlers.render_pre.append(self.pre)
        bpy.app.handlers.render_post.append(self.post)
        bpy.app.handlers.render_cancel.append(self.cancelled)

        # The timer gets created and the modal handler is added to the window manager
        self._timer = bpy.context.window_manager.event_timer_add(0.5, window=bpy.context.window)
        bpy.context.window_manager.modal_handler_add(self)

        return {"RUNNING_MODAL"}

    def modal(self, context, event):
        # This event is signaled every half a second and will start the render if available
        if event.type == 'TIMER':
            
            # If cancelled or no more shots to render, finish.
            if True in (not self.shots, self.stop is True): 
                # We remove the handlers and the modal timer to clean everything
                bpy.app.handlers.render_pre.remove(self.pre)
                bpy.app.handlers.render_post.remove(self.post)
                bpy.app.handlers.render_cancel.remove(self.cancelled)
                bpy.context.window_manager.event_timer_remove(self._timer)

                # I didn't separate the cancel and finish events, because in my case I don't need to, but you can create them as you need
                return {"FINISHED"} 

            # Nothing is currently rendering. Proceed to render.
            elif self.rendering is False: 
                # Get the scene
                scene = bpy.context.scene
                # Configure the camera
                scene.camera = bpy.data.objects[self.shots[0]] 	

                # Configure the file path
                localPath = self.path
                filePath = scene.render.filepath
                scene.render.filepath = RenderingHelpers.renderPath(localPath, filePath, self.shots[0], scene.render.file_extension)

                # Finally render the scene
                bpy.ops.render.render("INVOKE_DEFAULT", write_still=True)

        # This is very important! If we used "RUNNING_MODAL", this new modal function
        # would prevent the use of the X button to cancel rendering, because this
        # button is managed by the modal function of the render operator,
        # not this new operator!
        return {"PASS_THROUGH"}

        # This may prevent the rendering to run in the bakground when Blender is called from the command prompt.
        # The method can have other returns https://docs.blender.org/api/current/bpy.types.Operator.html#bpy.types.Operator.modal
        # RUNNING_MODAL would prevent the rendering cancel, but could make the bakground call run? NO, does not change anything.
        #
        # I think the modality is what is making the function exit early, because in background mode there is no modal (no GUI).

# ui part
class RbFilterSettings(bpy.types.PropertyGroup):
    rb_filter_enum: bpy.props.EnumProperty(
        name = "Filter",
        description = "Choose your destiny",
        items = [
            ("all", "All Cameras", "Render all cameras"),
            ("selected", "Selected Only", "Render selected only"),
        ],
        default = 'all'
    )   


class RenderBurstCamerasPanel(bpy.types.Panel):
    """Creates a Panel in the scene context of the properties editor"""
    bl_label = "Render Burst"
    bl_idname = "SCENE_PT_layout"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "render"

    def draw(self, context):
        wm = context.window_manager
        row = self.layout.row()
        row.prop(wm.rb_filter, "rb_filter_enum", expand=True)
        row = self.layout.row()
        row.operator("rb.renderbutton", text='Render!')
        row = self.layout.row()

class OBJECT_OT_RBButton(bpy.types.Operator):
    bl_idname = "rb.renderbutton"
    bl_label = "Render"

    #@classmethod
    #def poll(cls, context):
    #    return True
 
    def execute(self, context):
        if bpy.context.scene.render.filepath is None or len(bpy.context.scene.render.filepath)<1:
            self.report({"ERROR"}, 'Output path not defined. Please, define the output path on the render settings panel')
            return {"FINISHED"}

        animation_formats = [ 'FFMPEG', 'AVI_JPEG', 'AVI_RAW', 'FRAMESERVER' ]

        if bpy.context.scene.render.image_settings.file_format in animation_formats:
            self.report({"ERROR"}, 'Animation formats are not supported. Yet :)')
            return {"FINISHED"}

        bpy.ops.render.renderburst()
        return{'FINISHED'}

def menu_func(self, context):
    self.layout.operator(RenderBurst.bl_idname)

def register():
    from bpy.utils import register_class
    register_class(RenderBurst)
    register_class(RbFilterSettings)
    register_class(RenderBurstCamerasPanel)
    register_class(OBJECT_OT_RBButton)
    bpy.types.WindowManager.rb_filter = bpy.props.PointerProperty(type=RbFilterSettings)
    bpy.types.TOPBAR_MT_render.append(menu_func)

def unregister():
    from bpy.utils import unregister_class
    unregister_class(RenderBurst)
    bpy.types.TOPBAR_MT_render.remove(menu_func)
    unregister_class(RbFilterSettings)
    unregister_class(RenderBurstCamerasPanel)
    unregister_class(OBJECT_OT_RBButton)

if __name__ == "__main__":
    register()