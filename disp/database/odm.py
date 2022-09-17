"""
Object document mapping
"""

import datetime
from mongoengine import (Document, StringField, ReferenceField, DateTimeField,
                         EmbeddedDocumentField, EmbeddedDocument, FloatField,
                         IntField, DictField)
from fireworks.utilities.fw_utilities import get_my_host, get_my_ip

__all__ = ('Creator', 'DispEntry', 'SeedFile', 'ResProperty', 'ResFile',
           'InitialStructureFile', 'ParamFile')


class Creator(EmbeddedDocument):
    """Identity of the creator"""
    fw_id = IntField()
    uuid = StringField()
    ip_address = StringField(default=get_my_ip)
    hostname = StringField(default=get_my_host)
    fw_worker = DictField()


class DispEntry(Document):
    """
    DispEntry is primary document type for DISP related records

    Each entry should be associated with a project and seed, plus records of the creation times
    """
    project_name = StringField(required=True)  # Name of the project
    seed_name = StringField(required=True)  # Name of the seed
    created_on = DateTimeField(required=True, default=datetime.datetime.utcnow)
    content = StringField(
        required=True
    )  # Raw string field for the "content" of the entry. This maps to a small file.
    creator = EmbeddedDocumentField(Creator)  # Who created this document?
    meta = {'allow_inheritance': True, 'db_alias': 'disp'}


class SeedFile(DispEntry):
    """
    Representation of a search seed - the file used to generate the random structure
    """
    md5hash = StringField(
        max_length=40, required=True,
        unique=False)  # Require MD5 hash - used for deduplicate


class ResProperty(EmbeddedDocument):
    """
    Associated properties of a SHELX file.

    These information are parsed from the "content" field, used for easy querying and
    data retrival.
    """
    H = FloatField()  # Enthalpy   # pylint: disable=invalid-name
    P = FloatField()  # Pressure   # pylint: disable=invalid-name
    V = FloatField()  # Volume     # pylint: disable=invalid-name
    symm = StringField()  # Symmetry
    formula = StringField()  # The formula unit
    nform = IntField()  # Number of formula units
    spin = FloatField()  # Total spin
    abs_spin = FloatField()  # Absolute spin magnitude
    parallel_efficiency = FloatField()  # Parallel efficiency
    total_time = FloatField()  # Total run time
    pmg_structure = DictField()  # Pymatgen structure instance
    metadata = DictField()  # Any other metadata associated


class ResFile(DispEntry):
    """
    A representation of a SHELX file
    """
    struct_name = StringField()
    param_file = ReferenceField('ParamFile')
    seed_file = ReferenceField('SeedFile')
    init_structure_file = ReferenceField('InitialStructureFile')
    properties = EmbeddedDocumentField(ResProperty)
    res_type = StringField()


class ParamFile(DispEntry):
    """
    A representation of a ParamFile
    """
    md5hash = StringField(max_length=40, required=True,
                          unique=False)  # MD5 hash for deduplicate


class InitialStructureFile(DispEntry):
    """
    Representation of an initial structure for the search
    """
    struct_name = StringField()
    seed_file = ReferenceField('SeedFile', required=True)
