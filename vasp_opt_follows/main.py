"""
Follows different criterion of an optimization done with VASP.
Drop a `vaspout.h5` on the main window or use the "Open" button on top to get the graphs.
"""

import h5py
import matplotlib.figure
import numpy
from numpy.typing import NDArray
import sys
import threading
import pathlib
import gi

from typing import Self

from matplotlib.backends.backend_gtk4agg import FigureCanvasGTK4Agg as FigureCanvas
from matplotlib.backends.backend_gtk4 import NavigationToolbar2GTK4 as NavigationToolbar
from matplotlib.figure import Figure

import vasp_opt_follows

gi.require_version('Gtk', '4.0')
from gi.repository import GLib, Gtk, Gio, Gdk  # noqa


class VaspDataError(Exception):
    pass


class VaspOptData:
    def __init__(self, energies: NDArray[float], forces: NDArray[float], positions: NDArray[float]):

        # main quantities:
        self.energies = energies
        self.forces = forces
        self.positions = positions

    @classmethod
    def from_h5(cls, path: str) -> Self:
        with h5py.File(path, 'r') as f:
            # fetch data
            ion_dynamics = f['intermediate/ion_dynamics']

            energies = ion_dynamics['energies'][()]
            forces = ion_dynamics['forces'][()]
            positions = ion_dynamics['position_ions'][()]

            if '/input/poscar/selective_dynamics_ions' in f:
                # remove forces for non-selected DOF, as they may have a large force that is not taken into account
                mask = f['/input/poscar/selective_dynamics_ions'][()]
                pos_mask = numpy.where(mask == 0)
                forces[:, pos_mask] = .0

            return cls(energies, forces, positions)

    def make_graph(self, energy_label: int = 1) -> matplotlib.figure.Figure:
        # compute derived quantites to be plotted
        min_energy = numpy.min(self.energies[:, energy_label])
        dE = self.energies[1:, energy_label] - self.energies[:-1, energy_label]

        force_intensities = numpy.linalg.norm(self.forces, axis=2)

        forces_rms = numpy.sqrt(numpy.mean(force_intensities ** 2, axis=1))
        forces_max = numpy.max(force_intensities, axis=1)

        displacements = self.positions[1:] - self.positions[:-1]
        displacement_intensities = numpy.linalg.norm(displacements, axis=2)
        displacements_rms = numpy.sqrt(numpy.mean(displacement_intensities ** 2, axis=1))
        displacements_max = numpy.max(displacement_intensities, axis=1)

        ddisps = self.positions[1:] - self.positions[0]
        ddisps_intensities = numpy.linalg.norm(ddisps, axis=2)
        ddisps_sum = numpy.sum(ddisps_intensities, axis=1)

        # plot it
        X = numpy.arange(0, self.energies.shape[0])
        X2 = numpy.arange(1, self.energies.shape[0])
        fig = Figure(figsize=(6, 6), dpi=100)

        # 1. Energy
        ax = fig.add_subplot(311)
        ax.set_ylabel('Energy (eV)')
        ax.grid(axis='y')

        ax.plot(X, self.energies[:, energy_label] - min_energy, 'b-', label='Energies')

        secax = ax.twinx()
        secax.set_ylabel('|ΔE| (eV)')
        secax.set_yscale('log')

        secax.plot(X2, numpy.abs(dE))

        # 2. forces
        ax = fig.add_subplot(312)
        ax.set_ylabel('Forces (eV/Å)')
        ax.set_yscale('log')
        ax.grid(axis='y')

        ax.plot(X, forces_rms, 'g-', label='RMS')
        ax.plot(X, forces_max, 'r-', label='Max')

        ax.legend()

        # 3. disps
        ax = fig.add_subplot(313)
        ax.set_xlabel('steps')
        ax.set_ylabel('Displacements (Å)')
        ax.set_yscale('log')
        ax.grid(axis='y')

        ax.plot(X2, displacements_rms, 'g-', label='RMS')
        ax.plot(X2, displacements_max, 'r-', label='Max')

        ax.legend()

        secax = ax.twinx()
        secax.set_ylabel('|p[i]-p[0]| (Å)')

        secax.plot(X2, ddisps_sum)

        return fig


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

        # load data
        try:
            self.opt_data = VaspOptData.from_h5(path)
        except (OSError, KeyError, ValueError, VaspDataError) as e:
            make_error('Error while opening file', str(e))
            return

        # create graph
        fig = self.opt_data.make_graph()

        # make canvas+toolbar
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)

        canvas = FigureCanvas(fig)  # a Gtk.DrawingArea
        canvas.set_size_request(800, 600)
        vbox.append(canvas)

        toolbar = NavigationToolbar(canvas)
        vbox.append(toolbar)

        # replace child
        set_child(vbox)

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

        dialog.set_modal(self)

        dialog.connect('response', self.on_error_dialog_response)
        dialog.present()

    def on_error_dialog_response(self, dialog, response):
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

    def on_drop(self, target, value, x, y):
        self.open_vasp_h5(value)

    def on_open_clicked(self, button):
        dialog = Gtk.FileChooserDialog(
            transient_for=self,
            title='Please choose a file', action=Gtk.FileChooserAction.OPEN
        )

        dialog.set_modal(self)

        # buttons
        dialog.add_buttons(
            'Cancel',
            Gtk.ResponseType.CANCEL,
            'Open',
            Gtk.ResponseType.ACCEPT,
        )

        dialog.connect('response', self.on_response)
        dialog.present()

    def on_response(self, dialog, response):
        if response == Gtk.ResponseType.ACCEPT:
            self.open_vasp_h5(dialog.get_file())

        dialog.destroy()

    def on_about_clicked(self, button):
        about_dialog = Gtk.AboutDialog()
        about_dialog.set_transient_for(self)
        about_dialog.set_modal(self)

        about_dialog.set_program_name(pathlib.Path(__file__).name)
        about_dialog.set_authors([vasp_opt_follows.__author__])
        about_dialog.set_comments(__doc__)
        about_dialog.set_copyright('Copyright 2023 {}'.format(vasp_opt_follows.__author__))
        about_dialog.set_license_type(Gtk.License.MIT_X11)
        about_dialog.set_website('https://github.com/pierre-24/vasp-opt-follows')
        about_dialog.set_website_label('GitHub repository')
        about_dialog.set_version(vasp_opt_follows.__version__)

        about_dialog.set_visible(True)

    def open_vasp_h5(self, f):
        path = f.get_path()
        # create a dialog with the graph
        subwin = GraphWindow(path, transient_for=self)
        subwin.present()


class Application(Gtk.Application):
    def __init__(self):
        super().__init__(application_id='be.unamur.lct.vasp_opt_view')
        GLib.set_application_name('My Gtk Application')

        self.connect('open', self.on_open)
        self.set_flags(Gio.ApplicationFlags.HANDLES_OPEN)

    def do_activate(self):
        self.window = AppWindow(application=self, title='VASP optimization viewer')
        self.window.present()

    def on_open(self, app, files, n_files, hint):
        self.do_activate()  # Adding this because window may not have been created yet with this entry point
        for file in files:
            self.window.open_vasp_h5(file)


def main():
    app = Application()
    exit_status = app.run(sys.argv)
    sys.exit(exit_status)


if __name__ == '__main__':
    main()
