

from tunirdb import create_session, get_job
from tunirlib.default_config import DB_URL

def download_result(job_id=None):
    """
    Downloads the resultset in a file from the database.

    :param job_id: id of the job.
    :return: None
    """

    res = text_result(job_id)
    if not res:
        return
    name = 'result-%s.txt' % job_id
    with open(name, 'w') as fobj:
        fobj.write(res)


def text_result(job_id=None):
    """
    Returns a text version of the result.
    :param job_id: id of the job.
    :return: Text version of the report (unicode).
    """

    session = create_session(DB_URL)
    if not job_id:
        return

    result = u''
    job = get_job(session, job_id)
    if job.status:
        result = u"Passed.\n\n"
    else:
        result= u"Failed.\n\n"

    for res in job.results:
        result += u'command: %s\nstatus: %s\n' % (res.command, res.status)
        result += u'\n\n'

    return result