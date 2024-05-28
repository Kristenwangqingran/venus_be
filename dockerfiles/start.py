# -*- coding: utf-8 -*-
# @Time    : 2023-08-18
# @Author  : GongXun


import click
import os


class Worker:
    SYNC = 5
    EXEC = 2
    POSTWOMEN = 1
    HEALTH_CHECK = 1
    GOC = 1
    UPDATE_SPEX_API = 1
    STATISTIC = 4
    SHARE = 1
    PY = 2
    RPC = 5
    PFC = 14
    # The following three are not currently in use
    NOTIFICATION = 1
    CALLBACK = 10
    RECORD = 1
    CLEAN = 1


@click.command()
@click.option('--env', '-e', multiple=False, default='test', help="env type: test/live")
def main(env):
    """Command on exec"""

    click.secho(f"rq start...", fg='yellow')
    for name in dir(Worker):
        if not name.startswith('__') and name.isupper():
            count = getattr(Worker, name) if env == "live" else 1
            for i in range(1, count+1):
                click.secho(f"start {name} {i}", fg='green')
                os.system(f"(nohup flask rq worker {name.lower()} &)")

    os.system("flask rq worker")


if __name__ == '__main__':
    main()
