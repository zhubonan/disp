"""
Migration script
"""

from pymongo import MongoClient
from tqdm import tqdm


def migrate(target_db, target_coll, new_coll_name="disp_entry", client=None):
    """
    Migrate the database to the ODM style
    """
    if not client:
        client = MongoClient()
    database = client[target_db]
    col = database[target_coll]

    # Add class identifier
    col.update_many({"document_type": "res"}, {"$set": {"_cls": "DispEntry.ResFile"}})
    col.update_many({"document_type": "seed"}, {"$set": {"_cls": "DispEntry.SeedFile"}})
    col.update_many({"document_type": "param"}, {"$set": {"_cls": "DispEntry.ParmaFile"}})
    col.update_many({"document_type": "initial_structure"}, {"$set": {"_cls": "DispEntry.InitialStructureFile"}})

    print("Updated class identifier")

    # Remove the document type field
    col.update_many({"document_type": {"$exists": 1}}, {"$unset": {"document_type": ""}})

    print("Removed old identifier")
    # Remove the unused param_hash field
    col.update_many({"param_hash": {"$exists": 1}}, {"$unset": {"param_hash": ""}})

    col.update_many({"param_content": {"$exists": 1}}, {"$rename": {"param_content": "content"}})
    col.update_many({"seed_content": {"$exists": 1}}, {"$rename": {"seed_content": "content"}})
    col.update_many({"struct_content": {"$exists": 1}}, {"$rename": {"struct_content": "content"}})
    col.update_many({"res_content": {"$exists": 1}}, {"$rename": {"res_content": "content"}})

    print("Renamed xx_content fields")

    # Create index for md5hash
    col.create_index("md5hash", background=False)
    col.create_index("_cls", background=False)
    print("Linking SEED to ResFile and InitialStructureFile")
    query = {"_cls": {"$in": ["DispEntry.ResFile", "DispEntry.InitialStructureFile"]}}
    tot = col.count_documents(query)
    for entry in tqdm(list(col.find(query, projection=["seed_hash"])), total=tot):
        # Link seed_hash field
        if entry.get("seed_hash"):
            seed = col.find_one({"md5hash": entry["seed_hash"]})
            if seed:
                res = col.find_one_and_update({"_id": entry["_id"]}, {"$set": {"seed_file": seed["_id"]}})
                if not res:
                    print("Warning: cannot find the seed for {}".format(entry["struct_name"]))
    col.update_many(query, {"$unset": {"seed_hash": ""}})

    print("Linked seed to the ResFile and InitialStructureFile")

    print("Linking InitialStructureFile to ResFile")
    # Link the initial structures to the res files
    query = {"_cls": "DispEntry.InitialStructureFile"}
    tot = col.count_documents(query)
    for entry in tqdm(list(col.find(query, projection=["project_name", "seed_name", "struct_name"])), total=tot):
        res_entry = col.find_one(
            {
                "_cls": "DispEntry.ResFile",
                "project_name": entry["project_name"],
                "seed_name": entry["seed_name"],
                "struct_name": entry["struct_name"],
            }
        )
        # Link update the entry, not all have it
        if res_entry:
            col.find_one_and_update({"_id": res_entry["_id"]}, {"$set": {"init_structure_file": entry["_id"]}})

    print("Linked InitialStructureFile to the ResFile")

    print("Fixing the Creator Embedded document")
    query = {"creator": {"$exists": 1}}
    tot = col.count_documents(query)
    for entry in tqdm(list(col.find(query, projection=["creator"])), total=tot):
        # Migrate the creator field
        if entry.get("creator"):
            creator = entry["creator"]
            creator["uuid"] = creator["uuid"].hex
            creator["ip_address"] = creator.pop("ip", None)
            creator["hostname"] = creator.pop("host", None)
            col.find_one_and_update({"_id": entry["_id"]}, {"$set": {"creator": creator}})
    print("Creator Embedded document migrated")

    col.rename(new_coll_name)
    col = database[new_coll_name]

    print("Renamed collecte to `disp_entry`.")


if __name__ == "__main__":
    BASE_DB = "disp-archive"
    DB = "disp_migrate_test"
    COLLECTION = "disp-entries"

    # Reset the migration test collection
    client = MongoClient()
    base_coll = client[BASE_DB]["disp-entries"]
    migrate_coll = client[DB]["disp-entries"]
    migrate_coll.drop()
    print("Preparing migration test database")
    migrate_coll.insert_many(base_coll.find())
    for idx in ["seed_name", "project_name", "struct_name"]:
        migrate_coll.create_index(idx, background=False)
    # Drop the existing collection in the target database
    migrate(DB, COLLECTION)
