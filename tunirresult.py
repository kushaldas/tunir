

from tunirdb import create_session, get_job
from tunirlib.default_config import DB_URL

def download_result(job_id=None):
    """
    Downloads the resultset in a file from the database.

    :param job_id: id of the job.
    :return: None
    """

    session = create_session(DB_URL)
    if not job_id:
        return

    job = get_job(session, job_id)
    name = 'result-%s.txt' % job.id
    with open(name, 'w') as fobj:
        if job.status:
            fobj.write("Passed.\n\n")
        else:
            fobj.write("Failed.\n\n")

        for res in job.results:
            fobj.write('command: %s\nstatus: %s\n' % (res.command, res.status))
            fobj.write(res.output)
            fobj.write('\n\n')
