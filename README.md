# DISP (Distributed Structure Prediction)

Distribute the workload of structure searching (AIRSS) over flexible computing resources.
The process of searching for stable structure in AIRSS is trivially parallel, e.g. each worker does
the relaxation without any need of communication.

The traditional way is to launch an array of `airss.pl` job on HPC systems through the queue system.
The draw back of this method is that there is no way for continuing from unfinished jobs, and when
working with large systems the time for each relaxation can be on par with the job allocation time.
This limits the overall resource utilisation efficiency in AIRSS.

The other problem is to treat with CASTEP's SCF failures. It is possible that most of the time this does
not happen, but when it does the compute may cost a large amount of time to reach the SCF cycle limit.
Hence, it is desirable to use a smaller SCF cycle limit, but this in return increases the number of
failures. The hope is to add a system to recover from SCF failure and retry using different parameters.
