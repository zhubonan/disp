"""
Class for specialised worker for selecting jobs with walltime attached
Select jobs without walltime tags or those with tags and less than the limit.
"""

import six
from fireworks.core.fworker import FWorker

from disp.scheduler import Scheduler


class WalltimeAwareFWorker(FWorker):
    """
    Specialised worker for running jobs with walltime limits
    """

    SECONDS_SAFE_INTERVAL = 60

    def __init__(self, *args, **kwargs):
        """
        Instantiate a WalltimeAwareFWorker object.
        The worker selects the jobs to run depending on the time left.

        The rest of the arguments will be passed to the FWorker.
        """
        super().__init__(*args, **kwargs)
        self.scheduler = Scheduler.get_scheduler()

    @property
    def query(self):

        query = dict(self._query)
        fworker_check = [{"spec._fworker": {"$exists": False}}, {"spec._fworker": None}, {"spec._fworker": self.name}]
        if "$or" in query:
            query["$and"] = query.get("$and", [])
            query["$and"].extend([{"$or": query.pop("$or")}, {"$or": fworker_check}])
        else:
            query["$or"] = fworker_check
        if self.category and isinstance(self.category, str):
            if self.category == "__none__":
                query["spec._category"] = {"$exists": False}
            else:
                query["spec._category"] = self.category
        elif self.category:  # category is list of str
            query["spec._category"] = {"$in": self.category}

        # Either not having a walltime limit of have a one that is less than the
        # current limit
        walltime_condition = {
            "$or": [
                {"spec._walltime_seconds": {"$exists": 0}},
                {"spec._walltime_seconds": {"$lt": self.seconds_left - self.SECONDS_SAFE_INTERVAL}},
            ]
        }

        return {"$and": [query, walltime_condition]}

    @property
    def seconds_left(self):
        """
        How long this job is going to be alive.
        """
        return self.scheduler.get_remaining_seconds()
