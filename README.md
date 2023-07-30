# `vasp-opt-follows`

Follows different criterion of an optimization done with VASP.
In particular, looks into `vaspout.h5`, so [it requires to compile VASP with `-DVASP_HDF5`](https://www.vasp.at/wiki/index.php/Makefile.include#HDF5_support_.28strongly_recommended.29).

## Installation

This project requires the `PyGObject` of the GTK project to be set up. 
See [there](https://pygobject.readthedocs.io/en/latest/getting_started.html) for the installation steps for your system.

Then,

```bash
pip install git+https://github.com/pierre-24/vasp-opt-follows.git
```

## Usage

To launch the application:

```bash
vasp-opt-follows [vaspout.h5 [...]]
```

Then, drop any `vaspout.h5` file or use the "Open" button to open them.

## Contributing

See [there](https://pygobject.readthedocs.io/en/latest/getting_started.html) for the installation steps for `PyGObject`.

Then, [fork the repository](https://docs.github.com/en/get-started/quickstart/fork-a-repo), and:

```bash
# clone
git clone git@github.com:USERNAME/vasp-opt-follows.git
cd vasp-opt-follows

# create venv
python3 -m venv venv
source venv/bin/activate

# install stuffs, with dev tools
pip3 install -e .[dev] 
```