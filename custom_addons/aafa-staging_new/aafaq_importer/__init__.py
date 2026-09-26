# -*- coding: utf-8 -*-
from . import models
from . import wizard


def post_init_hook(env):
    env["aafaq.import.alias"]._retarget_held_mail_aliases()
