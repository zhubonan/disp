# Installation

A working setup of
[fireworks](https://materialsproject.github.io/fireworks/) is needed for
using this pacakge. This typically includes setting up a MongoDB server
that is both accessible by the local computer and the remote clusters
(compute nodes). The python
[fireworks](https://materialsproject.github.io/fireworks/) package needs
to be installed on both the local and the remote computers as well. The
MongoDB for managing the workflows is also used as a centralised
repository for holding the structure found by the search. Please refer
to the documentation of
[fireworks](https://materialsproject.github.io/fireworks/) for how to
setup it up.

As the MongoDB server also serves as a central storage for generated and
relaxed structures, sufficient storage space should be available to use.
Although usually the structure files (SHELX) format take relatively
small spaces.

The open sourced [AIRSS](https://www.mtg.msm.cam.ac.uk/Codes/AIRSS)
package also needs to be compiled and installed on both the remote and
local computers. This is necessary so that random structure can be
built, and its scripts shipped for running CASTEP calculations and
converting the results are needed as well.

Once the above is done, the DISP package can be installed using

``` none
pip install git+https://https://github.com/zhubonan/disp
```

This will install the package with its dependencies. After this the
command `disp` will be available to use.


# Database configuration

A MongoDB instanec is need for distributing work and storing relaxed structures.
For demostration and testing, a local MongoDB instance can be launched.
Docker is recommanded for running such temporary test database.

!!! example "Run mongodb using docker"

    ```
    sudo docker run -d -p 27017:27017 --name MONGO_CONTAINER mongo:4.4.9     
    ```

The standard way to access MongoDB is to use the mongo shell.
But using a GUI tool can also be very helpful, such as [Robo3T](https://robomongo.org/).

!!! example "Launch mongo shell through docker"

    ```
    sudo docker exec -it MONGO_CONTAINER mongo
    ```

For DISP to work, it needs to know how to connect to your database. 
The configurations are stored in two files, `my_launchpad.yaml` and `disp_db.yaml`.
The former is used by the fireworks workflow engine, and the latter is used by DISP itself for accessing 
the data.
In theory, you can have them poiting to difference servers, but it is not yet supported - make sure they have identical `host`, and `name`  and `database` should be the same as well.

The first one should look like:

```
host: localhost
port: 27017
name: disp-db-testing
username: null
password: null
ssl_ca_file: null
logdir: null
strm_lvl: INFO
user_indices: []
wf_user_indices: []
authsource: admin
```

and the second one:

```
host: localhost
port: 27017
database: disp-db-testing
collection: disp_entry
user: null
password: null
```

Note that for production database hosted on a remote server, you should enable authentication and put down your own username and password.

!!! note

    If these two files exists at the current working directory, they will be used by default.

For convenience, it is better to use environmental variable to select these files. 
The `DISP_DB_FILE` should be set and point to the location of the `disp_db.yaml` file.

The location of the `my_launchpad.yaml` should is set in a file called `FW_config.yaml`, 
which is a configuration files used for Fireworks.
On the remote compute, it is recommand to have a certain folder structure like below:

```
      <BASE_PATH>
      |- config
         | - FW_config.yaml
         | - disp_db.yaml
      |- airss-datastore
         |- <PROJECT_NAME>
      |....
```

The location of `FW_config.yaml` is determined from `$FW_CONFIG_FILE`, and the location of the `<BASE_PATH>` is implied from its value (or `$USER/airss-fw/` if not set).
Typically, the `disp_db.yaml` is in the same folder as `FW_config.yaml`.

When you launch a search through DISP, a `project_name` is passed, and it is used as a relative path insdie `airss-datastore` for storing detailed DFT output.
For example, search data from project `C2/100GPa/run1` will be placed into `<BASE_PATH>/airss-datastore/C2/100GPa/run1`

!!! note 

    It is worth setting both `FW_CONFIG_FILE` and `DISP_DB_FILE` in your `.bashrc`.


## Test configuration

A quick way to print out your configuration is to use:

```
disp check database
```


# Obtaining and compiling AIRSS

The AIRSS code can be downloaded from: https://www.mtg.msm.cam.ac.uk/Codes/AIRSS.


Note that for the 0.9.1 version the `external/spglib/makefile` needs to be updated.

??? code "Updated external/spglib/makefile"

    ```
    .DEFAULT:

    all: get libsymspg.a


    SPG_VERSION=1.9.4
    SPGLIB=spglib-$(SPG_VERSION)

    ifeq ($(SPG_VERSION), master)
    SPG_ARCHIVE=$(SPG_VERSION).zip
    else
    SPG_ARCHIVE=v$(SPG_VERSION).zip
    endif

    OBJ = $(SPGLIB)/src/arithmetic.o $(SPGLIB)/src/cell.o $(SPGLIB)/src/debug.o $(SPGLIB)/src/delaunay.o $(SPGLIB)/src/hall_symbol.o $(SPGLIB)/src/kgrid.o \
        $(SPGLIB)/src/kpoint.o $(SPGLIB)/src/mathfunc.o $(SPGLIB)/src/niggli.o $(SPGLIB)/src/pointgroup.o $(SPGLIB)/src/primitive.o \
        $(SPGLIB)/src/refinement.o $(SPGLIB)/src/site_symmetry.o $(SPGLIB)/src/sitesym_database.o $(SPGLIB)/src/spacegroup.o \
        $(SPGLIB)/src/spg_database.o $(SPGLIB)/src/spglib.o $(SPGLIB)/src/spin.o $(SPGLIB)/src/symmetry.o

    get:
        -wget -c --timeout=2 --tries=1 -nv https://github.com/atztogo/spglib/archive/v$(SPG_VERSION).zip
        -unzip -qq -u $(SPG_ARCHIVE) '$(SPGLIB)/src/*' '$(SPGLIB)/example/*'

    libsymspg.a: $(OBJ)
        -ar -cr $(PREFIX)/lib/libsymspg.a $(OBJ)
        -mkdir -p $(PREFIX)/include/spglib
        -cp $(SPGLIB)/src/spglib.h $(PREFIX)/include/spglib/spglib.h

    clean:
        -rm -fr $(SPGLIB)
    ```

Afterwards, `make && make install` will compile and install the executables to `bin` inside the code folder.
You will need to add the `bin` folder to your `PATH` variable.

Finally, check that AIRSS is working with `make check`.
AIRSS should be installed on any computer that runs structure search workload.

!!! note

    You may want to use a newer version of AIRSS if possible.

