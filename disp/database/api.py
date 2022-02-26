"""
Module for providing a MongoDB database (collection) interface for AIRSS searches
"""
import os
import zlib
import enum
from logging import getLogger, INFO, WARNING
import hashlib
import time
from datetime import datetime, timedelta

from monty.serialization import loadfn
from fireworks.utilities.fw_utilities import get_my_host, get_my_ip

import pymongo
from pymongo import MongoClient
from pymongo.errors import PyMongoError
import gridfs
import pandas as pd

from mongoengine import connect, get_connection
from mongoengine.connection import ConnectionFailure
from disp.database.odm import (ResFile, ParamFile, SeedFile,
                               InitialStructureFile, Creator)

# pylint: disable=too-many-instance-attributes, too-many-arguments, import-outside-toplevel, no-member, protected-access


def get_db_file_path():
    """Returns the path of the db file"""
    return os.environ.get('DISP_DB_FILE')


DB_FILE = get_db_file_path()


class DocumentType(enum.Enum):

    RES = 'res'
    SEED = 'seed'
    INITIAL_STRUCTURE = 'initial_structure'
    PARAM = 'param'


class SearchDB:
    """
    Database backend for storing search results
    """
    logger = getLogger(__name__)
    INDICIES = [
        'project_name', 'seed_name', 'created_on', 'md5hash', 'struct_name'
    ]
    _ATOMATE_TASK_COLL = 'atomate_tasks'  # Name of the collection for atomate tasks
    INDICIES_ATOMATE_TASKS = [
        'project_name', 'seed_name', 'struct_name', 'uuid', 'unique_name',
        'task_label', 'disp_type', 'last_updated'
    ]

    def __init__(self,
                 host: str = 'localhost',
                 port: int = 27017,
                 database: str = 'disp-db',
                 user: str = None,
                 password: str = None,
                 collection: str = 'disp_entry',
                 **kwargs):

        self.host = host
        self.db_name = database
        self.user = user
        self.password = password
        self.port = int(port)
        self.identity = {}
        try:
            self._engine_connection = connect(db=self.db_name,
                                              alias='disp',
                                              host=host,
                                              username=user,
                                              port=int(port),
                                              password=password,
                                              authentication_source=kwargs.get(
                                                  'authsource', None))
        except ConnectionFailure:
            self.logger.info('Reusing existing connections')
            self._engine_connection = get_connection('disp')

        # Direct connection with PyMongo
        try:
            self.connection = MongoClient(host=self.host,
                                          port=self.port,
                                          username=self.user,
                                          password=self.password,
                                          **kwargs)
            self.database = self.connection[self.db_name]
        except PyMongoError:
            self.logger.error('Mongodb connection failed')
            raise RuntimeError

        # Authenticate through pymongo
        try:
            if self.user:
                self.database.authenticate(self.user,
                                           self.password,
                                           source=kwargs.get(
                                               'authsource', None))
        except PyMongoError:
            self.logger.error('Mongodb authentication failed')
            raise RuntimeError
        self.collection = self.database[collection]
        self.gfs = gridfs.GridFS(self.database, collection=collection + '-fs')

    def set_identity(self, fw_id, uuid=None, fw_worker=None):
        """Populate the identity dictionary"""
        self.identity['fw_id'] = fw_id
        if uuid:
            self.identity['uuid'] = uuid
        self.identity['hostname'] = get_my_host()
        self.identity['ip_address'] = get_my_ip()
        if fw_worker:
            self.identity['fw_worker'] = fw_worker

    def include_creator(self, entry):
        """Return a 'Creator' embedded document for recording the creator of any created document"""
        if self.identity:
            entry.creator = Creator(**self.identity)

    def build_indexes(self, additional_fields=None, background=True):
        """
         Build the indexes to accelerate queries
         Args:
             indexes (list): list of single field indexes to be built.
             background (bool): Run in the background or not.
        """
        if additional_fields is None:
            additional_fields = []
        _indices = list(self.INDICIES)
        _indices.extend(additional_fields)

        for key in _indices:
            self.collection.create_index(key, background=background)

        # Create compound index for project_name and seed_name
        for key in ['project_name', 'seed_name']:
            self.collection.create_index([(key, pymongo.DESCENDING),
                                          ('created_on', pymongo.DESCENDING)])

        # Build indices for atomate tasks collection
        for key in self.INDICIES_ATOMATE_TASKS:
            self.database[self._ATOMATE_TASK_COLL].create_index(
                key, background=background)

        # Create compound index for project_name and seed_name
        for key in ['project_name', 'seed_name']:
            self.database[self._ATOMATE_TASK_COLL].create_index([
                (key, pymongo.DESCENDING), ('last_update', pymongo.DESCENDING)
            ])

    def insert_seed(self, project_name: str, seed_name: str,
                    seed_content: str):
        """Insert a single record of the seed for structure generation"""
        md5hash = hashlib.md5(seed_content.encode()).hexdigest()
        seed = SeedFile.objects(md5hash=md5hash,
                                project_name=project_name,
                                seed_name=seed_name).first()
        if not seed:
            seed = SeedFile(md5hash=md5hash,
                            seed_name=seed_name,
                            content=seed_content,
                            project_name=project_name)
            self.include_creator(seed)
            seed.save()
        return seed

    def insert_param(self, project_name: str, param_content: str,
                     seed_name: str):
        """Insert a single record for paramter"""

        md5hash = hashlib.md5(param_content.encode()).hexdigest()
        param = ParamFile.objects(md5hash=md5hash,
                                  project_name=project_name).first()
        if not param:
            param = ParamFile(md5hash=md5hash,
                              content=param_content,
                              project_name=project_name,
                              seed_name=seed_name)
            self.include_creator(param)
            param.save()
        return param

    def insert_search_record(self,
                             project_name: str,
                             struct_name: str,
                             res_content: str,
                             param_content=None,
                             seed_name=None,
                             seed_hash=None,
                             seed_content=None):
        """Insert a record of the resultant structure of a search"""

        if seed_hash and seed_content:
            md5hash = hashlib.md5(seed_content.encode()).hexdigest()
            assert md5hash == seed_hash, 'The seed_hash does not match seed_content!!'

        # Seed content supplied but no hash given - insert this seed to the database
        if (not seed_hash) and seed_name and seed_content:
            seed_file = self.insert_seed(project_name, seed_name, seed_content)
        else:
            seed_file = None

        if param_content:
            param_file = self.insert_param(project_name, param_content,
                                           seed_name)
        else:
            param_file = None

        res_record = ResFile(seed_name=seed_name,
                             project_name=project_name,
                             content=res_content,
                             struct_name=struct_name)
        # Link to the Param and Seed files
        res_record.param_file = param_file
        res_record.seed_file = seed_file
        self.include_creator(res_record)

        # Link with the initial structure of this record
        # Link to the last record in case of Firework level rerun
        init = InitialStructureFile.objects(
            project_name=project_name,
            seed_name=seed_name,
            struct_name=struct_name).order_by('-created_on').first()
        if init:
            res_record.init_structure_file = init

        res_record.save()
        return res_record

    def insert_initial_structure(self, project_name: str, struct_name: str,
                                 struct_content: str, seed_name: str,
                                 seed_content: str):
        """Insert a record of a randomly generated structure"""
        seed_file = self.insert_seed(project_name, seed_name, seed_content)
        init_structure = InitialStructureFile(project_name=project_name,
                                              struct_name=struct_name,
                                              seed_name=seed_name,
                                              content=struct_content)
        init_structure.seed_file = seed_file
        self.include_creator(init_structure)
        init_structure.save()
        return init_structure

    @staticmethod
    def retrieve_project(project_name: str,
                         include_seed=False,
                         include_param=False,
                         additional_filters=None,
                         include_initial_structure=False):
        """
        Retrieve all results from a single projection

        Args:
          project_name: Name of the projection to query
          include_seed: Include the content of thhe seed in the result.
          include_param: Include the 'param' file content in the result.
          include_initial_structure: Include initial structures

        Returns:
          list: a QuerySet object containing the ResFile instances
        """
        qset = ResFile.objects(project_name=project_name)
        if not include_seed:
            qset = qset.exclude('seed_file')
        if not include_initial_structure:
            qset = qset.exclude('init_structure_file')
        if not include_param:
            qset = qset.exclude('param_file')
        if additional_filters:
            qset = qset.filter(__raw__=additional_filters)
        return qset.all()

    @staticmethod
    def get_summary_df(projects=None, seeds=None):
        """
        Summarise the database using pandas.DataFrame

        Generate a report for the status of the database. Not including the
        actual content of the seed.
        """
        res = ResFile.objects()

        if projects:
            res = res.filter(project_name__in=projects)
        if seeds:
            res = res.filter(seed_name__in=seeds)
        fields = ['seed_name', 'project_name', 'created_on', 'struct_name']
        res = res.only(*fields)
        # Here we use what is not part of the public API....
        results = [rfile._data for rfile in res]
        if results:
            dataframe = pd.DataFrame(results)[fields]
            return dataframe
        return pd.DataFrame([], columns=fields)

    def throughput_summary(self,
                           past_days=2,
                           start_date=None,
                           projects=None,
                           seeds=None,
                           aggregate='H',
                           group_by='seed_name',
                           plot=True):
        """
        Summarise the througput of search

        Args:
          projects(list): List of projects to include
          seeds(list): :List of seeds to include

        Returns:
          A dataframe of search results per hour
        """
        import matplotlib.pyplot as plt

        query = ResFile.objects()
        if projects:
            query = query.filter(project_name__in=projects)
        if seeds:
            query = query.filter(seed_name__in=seeds)

        now = datetime.utcnow()
        if start_date is None:
            dstart = now - timedelta(days=past_days)
        else:
            dstart = datetime.strptime(start_date, '%Y-%m-%d')
        dfinish = dstart + timedelta(days=past_days)
        query = query.filter(created_on__gte=dstart, created_on__lte=dfinish)

        included = ['id', 'created_on', 'seed_name', 'project_name']
        query = query.only(*included)
        results = [resfile._data for resfile in query]

        if not results:
            self.logger.warning('No structure is found.')
            return None

        # Add in worker information
        dataframe = pd.DataFrame(results)[included]
        if group_by == 'worker_name':
            worker_res = query.aggregate(worker_aggregation())
            worker_info = pd.DataFrame(worker_res)
            worker_info['worker_name'] = worker_info['worker_name'].apply(
                lambda x: x[0] if x else None)
            dataframe = dataframe.merge(worker_info,
                                        left_on='id',
                                        right_on='_id',
                                        how='left')
        dataframe.set_index('created_on', inplace=True)
        dataframe['uid'] = [
            row.project_name + ':' + row.seed_name
            for _, row in dataframe.iterrows()
        ]

        #dataframe = dataframe.set_index('created_on', inplace=True)

        tdf = dataframe.groupby(group_by).resample(
            aggregate)[group_by].count().unstack(level=0)
        tdf.name = 'Completed'
        if plot:
            tdf.index = tdf.index.tz_localize('UTC').tz_convert('Europe/London')
            tdf.index = [x.strftime('%d/%m %H00') for x in tdf.index]
            tdf.plot.bar(stacked=True)
            plt.xlabel('Creation time')
            plt.ylabel('Count')
            plt.title('New structures')
            plt.tight_layout()
            plt.legend(loc=None)
            plt.show()
        else:
            # Save the data
            tdf.to_csv('throughput.csv')


        return tdf

    def throughput_summary_atomate(self,
                                   past_days=2,
                                   start_date=None,
                                   projects=None,
                                   seeds=None,
                                   aggregate='H',
                                   group_by='seed_name',
                                   plot=True):
        """
        Summarise the througput of atomate calculations.

        Args:
          projects (list): List of projects to include
          seeds (list): :List of seeds to include

        Returns:
          A dataframe of search results per hour
        """
        import matplotlib.pyplot as plt

        task_coll = self.database[self._ATOMATE_TASK_COLL]
        query = {}
        if projects:
            query['project_name'] = {'$in': projects}
        if seeds:
            query['seed_name'] = {'$in': seeds}

        if start_date is None:
            dstart = datetime.utcnow() - timedelta(days=past_days)
        else:
            dstart = datetime.strptime(start_date, '%Y-%m-%d')
        query['last_updated'] = {
            '$gte': dstart,
            '$lte': dstart + timedelta(days=past_days)
        }

        included = ['last_updated', 'seed_name', 'project_name', 'dir_name']
        results = list(task_coll.find(query, included))

        if not results:
            self.logger.warning('No structure is found.')
            return None

        # Add in worker information
        dataframe = pd.DataFrame(results)[included]
        dataframe.dropna(inplace=True)
        dataframe['uid'] = [
            row.project_name + ':' + row.seed_name
            for _, row in dataframe.iterrows()
        ]
        machine = []
        for value in dataframe['dir_name']:
            host = value.split(':')[0]
            if '.' in host:
                host = host.split('.',
                                  1)[1]  # Skip the first part of the hostname
            machine.append(host)
        dataframe['worker_name'] = machine

        dataframe.set_index('last_updated', inplace=True)

        dataframe = dataframe.groupby(group_by).resample(
            aggregate)[group_by].count().unstack(level=0)

        dataframe.name = 'Completed'
        dataframe.index = dataframe.index.tz_localize('UTC').tz_convert(
            'Europe/London')
        if plot:
            dataframe.plot.bar(stacked=True)
            plt.xlabel('Creation time')
            plt.xlabel('Count')
            plt.title('Completed Calculations')
            plt.tight_layout()
            plt.show()
        else:
            # Save the data
            dataframe.to_csv('throughput.csv')

        return dataframe

    def show_struct_counts(self,
                           project_regex=None,
                           seed_regex=None,
                           states=None,
                           include_workflows=True,
                           include_atomate=False,
                           show_priority=False,
                           include_res=True,
                           verbose=False):
        """
        Display count of the structures
        """
        if include_workflows and not include_atomate:
            wf_mode = 'search'
        elif include_atomate:
            wf_mode = 'ato'
        else:
            wf_mode = 'none'

        counter = StructCounts(self.collection,
                               self.database.fireworks,
                               self.database.workflows,
                               states=states,
                               seed_regex=seed_regex,
                               project_regex=project_regex,
                               wf_mode=wf_mode,
                               show_priority=show_priority,
                               include_res=include_res,
                               verbose=verbose)
        return counter.get_summary_df()

    @classmethod
    def from_db_file(cls, db_file: str):
        """
        Create from a database file. File requires host, port, database,
        collection, username and password
        Args:
            db_file (str): path to the file containing the credentials
        Returns:
            MMDb object
        """
        creds = loadfn(db_file)

        user = creds.get('user')
        password = creds.get('password')

        kwargs = creds.get('mongoclient_kwargs',
                           {})  # any other MongoClient kwargs can go here ...

        if 'authsource' in creds:
            kwargs['authsource'] = creds['authsource']
        else:
            kwargs['authsource'] = creds['database']

        return cls(host=creds['host'],
                   port=int(creds.get('port', 27017)),
                   database=creds['database'],
                   collection=creds['collection'],
                   user=user,
                   password=password,
                   **kwargs)

    def upload_dot_castep(self, struct_name, seed_name, project_name):
        """Update the dot CASTEP files"""
        fname = struct_name + '.castep'
        query = {
            'struct_name': struct_name,
            'seed_name': seed_name,
            'project_name': project_name
        }
        if self.gfs.exists(query):
            raise FileExistsError(f'File {fname} exists already')

        with open(fname, 'rb') as fhandle:
            content = zlib.compress(fhandle.read())

        self.gfs.put(content,
                     filename=fname,
                     project_name=project_name,
                     seed_name=seed_name,
                     struct_name=struct_name)

    def retrieve_dot_castep(self, struct_name, seed_name, project_name):
        """Retrieve a dot CASTEP file"""
        fname = struct_name + '.castep'
        query = {
            'struct_name': struct_name,
            'seed_name': seed_name,
            'project_name': project_name
        }
        gfile = self.gfs.find_one(query)
        if not gfile:
            raise FileNotFoundError(f'Cannot found {fname}!')

        content = gfile.read()
        with open(fname, 'wb') as fhandle:
            fhandle.write(zlib.decompress(content))

    def delete_dot_castep(self, struct_name, seed_name, project_name):
        """Delete dot CASTEP files"""
        query = {
            'struct_name': struct_name,
            'seed_name': seed_name,
            'project_name': project_name
        }

        to_delete = []
        for gfile in self.gfs.find(query):
            to_delete.append(gfile._id)  # pytest: disable=protected-access

        for _id in to_delete:
            self.gfs.delete(_id)


def get_hash(string):
    """Returns the md5hash for a string"""
    return hashlib.md5(string.encode()).hexdigest()


def get_pipeline(cls_string,
                 project_regex=None,
                 seed_regex=None,
                 projects=None,
                 seeds=None):
    """
    Obtain the pipline for querying SearchDB
    """
    pipeline = [{
        '$match': {
            '_cls': cls_string
        }
    }, {
        '$group': {
            '_id': {
                'seed': '$seed_name',
                'project': '$project_name'
            },
            'count': {
                '$sum': 1
            }
        }
    }]

    # Add regular expression matches
    if project_regex:
        pipeline[0]['$match']['project_name'] = {'$regex': project_regex}
    if seed_regex:
        pipeline[0]['$match']['seed_name'] = {'$regex': seed_regex}
    # Query directly by list of seeds/projects - this overrides the regex options
    if projects:
        pipeline[0]['$match']['project_name'] = {'$in': projects}
    if seeds:
        pipeline[0]['$match']['seed_name'] = {'$in': seeds}

    return pipeline


def get_atomate_wflows(wf_coll, states, seed_regex=None,
                       project_regex=None) -> pd.DataFrame:
    """Obtain workflow informaton for atomate jobs"""
    return get_workflows(wf_coll, ['atomate-relax'],
                         states,
                         seed_regex=seed_regex,
                         project_regex=project_regex)


def get_std_wflows(wf_coll, states, seed_regex=None,
                   project_regex=None) -> pd.DataFrame:
    """Obtain workflow informaton for standard search jobs"""
    return get_workflows(wf_coll, ['relax', 'search'],
                         states,
                         seed_regex=seed_regex,
                         project_regex=project_regex)


def get_workflows(wf_coll,
                  disp_types,
                  states,
                  seed_regex=None,
                  project_regex=None) -> pd.DataFrame:
    """Obtain atomate workflows matching certain criteria"""
    query = {}
    if seed_regex:
        query['metadata.seed_name'] = {'$regex': seed_regex}
    if project_regex:
        query['metadata.project_name'] = {'$regex': project_regex}
    if states:
        query['state'] = {'$in': states}

    query['metadata.disp_type'] = {'$in': disp_types}

    projection = ['state', 'metadata']
    cursor = wf_coll.find(query, projection)
    records = []
    for entry in cursor:
        dtmp = {
            'state': entry['state'],
        }
        dtmp.update(entry['metadata'])
        records.append(dtmp)
    return pd.DataFrame(records)


def worker_aggregation(launch_col='launches'):
    """
    Find the worker identify for each creator.fw_id
    """
    pipline = [{'$project': {'_id': 1, 'creator.fw_id': 1}}]

    lookup_stage = {
        '$lookup': {
            'from':
            launch_col,
            'let': {
                'creator_id': '$creator.fw_id'
            },
            'as':
            'launch',
            'pipeline': [{
                '$match': {
                    '$expr': {
                        '$and': [{
                            '$eq': ['$fw_id', '$$creator_id']
                        }, {
                            '$eq':
                            ['$action.stored_data.relax_status', 'FINISHED']
                        }]
                    }
                }
            }, {
                '$project': {
                    'fworker.name': 1
                }
            }]
        }
    }

    pipline.append(lookup_stage)

    # Project worker name to the top level
    project_stage = {'$project': {'worker_name': '$launch.fworker.name'}}

    pipline.append(project_stage)
    return pipline


class StructCounts:
    """Class for querying the database to obtain the structure counts"""

    def __init__(self,
                 disp_coll: str,
                 fw_coll: str,
                 wf_coll: str,
                 states=None,
                 seed_regex=None,
                 project_regex=None,
                 wf_mode='search',
                 show_priority=False,
                 include_res=True,
                 verbose=True):
        """Initialise a StructCounts object"""
        self.disp_coll = disp_coll
        self.fw_coll = fw_coll
        self.wf_coll = wf_coll
        self.states = states
        self.seed_regex = seed_regex
        self.project_regex = project_regex
        self.seeds = []
        self.projects = []
        self.verbose = verbose
        self.wf_mode = wf_mode
        self.show_priority = show_priority  # Not used
        self.include_res = include_res  # Query the structure counts
        self.logger = getLogger(__name__)
        if verbose:
            self.logger.setLevel(INFO)
        else:
            self.logger.setLevel(WARNING)

    def get_summary_df(self):
        """Main loginc for getting the summary of the data"""

        # First, obtain the workflows to be included
        if self.verbose:
            self.logger.info('Collecting workflow information')
            ttmp = time.time()

        # This would set some filters - based on the state and selected projects
        wdf = self.get_wf_collection()

        if len(wdf) == 0:
            self.logger.info('No workflow matches the query.')
            if self.projects is not None or self.seeds is None:
                return wdf

        if self.verbose:
            ttmp = time.time() - ttmp
            self.logger.info(
                'Workflow information collected - time elapsed: %.2f s', ttmp)

        sdf, idf = self.get_res_entries()

        # No relaxed structures - just return the workflow information
        if len(sdf) == 0 or not self.include_res:
            return wdf

        # Get summary of the relaxed / initial structures
        struct_count = sdf.groupby(['project', 'seed'])[['res']].sum()
        init_count = idf.groupby(['project', 'seed'])[['init_structs']].sum()
        try:
            final_df = struct_count.merge(init_count,
                                          left_index=True,
                                          right_index=True,
                                          how='outer')
        except ValueError:
            final_df = struct_count.copy()
            final_df['init_structures'] = 0.0

        final_df.columns = pd.MultiIndex.from_tuples([('Structure', 'RES'),
                                                      ('Structure', 'Init')])

        # Blend in workflow information
        if len(wdf) > 0:
            final_df = final_df.merge(wdf,
                                      left_index=True,
                                      right_index=True,
                                      how='right')

        # Fill NaN as 0.0
        final_df = final_df.fillna(0.0)
        return final_df

    def get_wf_collection(self):
        """Get atomate workflow statistics"""
        if self.wf_mode == 'search':

            wf_records = get_std_wflows(self.wf_coll, self.states,
                                        self.seed_regex, self.project_regex)
        elif self.wf_mode == 'ato':
            wf_records = get_atomate_wflows(self.wf_coll, self.states,
                                            self.seed_regex,
                                            self.project_regex)
        else:
            raise ValueError(f'Unknown wf_mode: {self.wf_mode}')

        if len(wf_records) != 0:
            # Group data by project_name, 'seed_name' and 'state' then unstack
            wf_df = wf_records.groupby(['project_name', 'seed_name', 'state'
                                        ]).count().unstack()[['disp_type'
                                                              ]].fillna(0.0)
            wf_df[('disp_type', 'ALL')] = wf_df.sum(axis=1)
            wf_df = wf_df.rename(
                columns={'disp_type': f'WF count - {self.wf_mode}'})
            wf_df.columns.names = [None, None]
            wf_df.index.names = ['project', 'seed']
            # If no contrains on the seeds / projects is imposed, use the workflow results to
            # limit them
            if self.seed_regex is None:
                self.projects = wf_records.project_name.unique().tolist()
            if self.project_regex is None:
                self.seeds = wf_records.seed_name.unique().tolist()
        else:
            # NO entry - return an empty dataframe
            wf_df = pd.DataFrame()

        return wf_df

    def get_res_entries(self):
        """Obtain the entry of res files"""
        ttmp = time.time()

        # Check if any filters have been applied - warning if thait is not the case
        has_no_filter = all(
            tmp is None for tmp in
            [self.project_regex, self.projects, self.seeds, self.seed_regex])
        if has_no_filter:
            self.logger.info(
                'WARNING: No effective filters applied - projecting the entire database!!'
            )

        # Find the SHELX entries for the matching entries
        res = self.disp_coll.aggregate(
            get_pipeline('DispEntry.ResFile',
                         project_regex=self.project_regex,
                         projects=self.projects,
                         seeds=self.seeds,
                         seed_regex=self.seed_regex))
        data = [(item['_id']['seed'], item['_id']['project'], item['count'])
                for item in res]
        sdf = pd.DataFrame(data, columns=['seed', 'project', 'res'])
        dtime = time.time() - ttmp
        self.logger.info(
            f'Obtained relaxed structure counts - time elapsed {dtime:.2f}'
        )

        # Include initial structures
        ttmp = time.time()
        res = self.disp_coll.aggregate(
            get_pipeline('DispEntry.InitialStructureFile',
                         project_regex=self.project_regex,
                         seed_regex=self.seed_regex,
                         projects=self.projects,
                         seeds=self.seeds))
        data = [(item['_id']['seed'], item['_id']['project'], item['count'])
                for item in res]
        idf = pd.DataFrame(data, columns=['seed', 'project', 'init_structs'])

        dtime = time.time() - ttmp
        self.logger.info(
            f'Obtained initial structure counts - time elapsed {dtime:.2f} s'
        )

        return sdf, idf
