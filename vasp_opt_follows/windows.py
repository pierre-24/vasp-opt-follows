import pathlib
import threading
import gi

from matplotlib.backends.backend_gtk4 import NavigationToolbar2GTK4 as NavigationToolbar
from matplotlib.backends.backend_gtk4agg import FigureCanvasGTK4Agg as FigureCanvas

import vasp_opt_follows
from vasp_opt_follows.data import VASPData, VASPDataError

gi.require_version('Gtk', '4.0')
from gi.repository import GLib, Gtk, Gio, Gdk  # noqa


class GraphWindow(Gtk.Dialog):
    MARGIN = 16

    def __init__(self, path: str, **kwargs):
        super().__init__(title=path, **kwargs)

        label = Gtk.Label(label='Opening, please wait...')
        label.set_margin_top(self.MARGIN)
        label.set_margin_bottom(self.MARGIN)
        label.set_margin_start(self.MARGIN)
        label.set_margin_end(self.MARGIN)
        self.set_child(label)

        # load data in thread
        self.opt_data = None
        thread = threading.Thread(target=self.load_data, args=(path,))
        thread.daemon = True
        thread.start()

    def load_data(self, path: str):
        """Threaded loading (see https://pygobject.readthedocs.io/en/latest/guide/threading.html)"""

        def make_error(title: str, message: str):
            def do_event(event, result):
                self.show_error(title, message)
                event.set()

            event = threading.Event()
            GLib.idle_add(do_event, event, [])
            event.wait()

        def set_child(child):
            def do_event(event, result):
                self.set_child(child)
                event.set()

            event = threading.Event()
            GLib.idle_add(do_event, event, [])
            event.wait()

        def make_notebook_page(graph) -> Gtk.Box:
            vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
            canvas = FigureCanvas(graph)
            canvas.set_size_request(800, 600)
            vbox.append(canvas)
            toolbar = NavigationToolbar(canvas)
            vbox.append(toolbar)

            return vbox

        # load data
        try:
            self.opt_data = VASPData.from_h5(path)
        except (OSError, KeyError, ValueError, VASPDataError) as e:
            make_error('Error while opening file', str(e))
            return

        # create graphs
        fig_energy, fig_position = self.opt_data.make_graphs()

        # create notebook
        notebook = Gtk.Notebook()
        notebook.append_page(make_notebook_page(fig_energy), Gtk.Label(label='Energy and forces'))
        notebook.append_page(make_notebook_page(fig_position), Gtk.Label(label='Positions and lattice'))

        # replace child with notebook
        set_child(notebook)

    def show_error(self, title: str, message: str):
        """Show the error in `MessageDialog`
        """

        dialog = Gtk.MessageDialog(
            transient_for=self,
            message_type=Gtk.MessageType.ERROR,
            buttons=Gtk.ButtonsType.OK,
            title=title,
            text=message,
        )

        dialog.set_modal(True)

        dialog.connect('response', self.on_error_dialog_response)
        dialog.present()

    def on_error_dialog_response(self, dialog: Gtk.MessageDialog, response: int):
        """Destroy both the dialog and the underlying window, since there will be nothing to show here"""

        dialog.destroy()
        self.destroy()


class AppWindow(Gtk.ApplicationWindow):
    MARGIN = 32

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        # a label
        hbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.set_child(hbox)

        label = Gtk.Label()
        label.set_markup('Drop a `vaspout.h5` here or open them using the button above.')
        label.set_margin_top(self.MARGIN)
        label.set_margin_bottom(self.MARGIN)
        label.set_margin_start(self.MARGIN)
        label.set_margin_end(self.MARGIN)
        hbox.append(label)

        # add a header with a "Open" button
        self.header = Gtk.HeaderBar()
        self.set_titlebar(self.header)

        open_button = Gtk.Button(label='Open')
        open_button.set_icon_name('document-open-symbolic')
        open_button.connect('clicked', self.on_open_clicked)
        self.header.pack_start(open_button)

        about_button = Gtk.Button(label='About this program')
        about_button.set_icon_name('help-about')
        about_button.connect('clicked', self.on_about_clicked)
        self.header.pack_start(about_button)

        # add a drop_target
        drop_target = Gtk.DropTarget(actions=Gdk.DragAction.COPY, formats=Gdk.ContentFormats.new_for_gtype(Gio.File))
        drop_target.connect('drop', self.on_drop)
        self.add_controller(drop_target)

    def on_drop(self, target, value, x: float, y: float):
        self.open_vasp_h5(value)

    def on_open_clicked(self, button: Gtk.Button):
        dialog = Gtk.FileChooserDialog(
            transient_for=self,
            title='Please choose a file', action=Gtk.FileChooserAction.OPEN
        )

        dialog.set_modal(True)

        # buttons
        dialog.add_buttons(
            'Cancel',
            Gtk.ResponseType.CANCEL,
            'Open',
            Gtk.ResponseType.ACCEPT,
        )

        dialog.connect('response', self.on_response)
        dialog.present()

    def on_response(self, dialog: Gtk.FileChooserDialog, response: Gtk.ResponseType):
        if response == Gtk.ResponseType.ACCEPT:
            self.open_vasp_h5(dialog.get_file())

        dialog.destroy()

    def on_about_clicked(self, button: Gtk.Button):
        about_dialog = Gtk.AboutDialog()
        about_dialog.set_transient_for(self)
        about_dialog.set_modal(True)

        about_dialog.set_program_name(pathlib.Path(__file__).name)
        about_dialog.set_authors([vasp_opt_follows.__author__])
        about_dialog.set_comments(vasp_opt_follows.__doc__)
        about_dialog.set_copyright('Copyright 2023 {}'.format(vasp_opt_follows.__author__))
        about_dialog.set_license_type(Gtk.License.MIT_X11)
        about_dialog.set_website('https://github.com/pierre-24/vasp-opt-follows')
        about_dialog.set_website_label('GitHub repository')
        about_dialog.set_version(vasp_opt_follows.__version__)

        about_dialog.set_visible(True)

    def open_vasp_h5(self, f: Gio.File):
        path = f.get_path()

        # create a dialog with the graph
        subwin = GraphWindow(path, transient_for=self)
        subwin.present()
