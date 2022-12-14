# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements.  See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership.  The ASF licenses this file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License.  You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an
# "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
# KIND, either express or implied.  See the License for the
# specific language governing permissions and limitations
# under the License.
#
# This file is included in the final Docker image and SHOULD be overridden when
# deploying the image to prod. Settings configured here are intended for use in local
# development environments. Also note that superset_config_docker.py is imported
# as a final step as a means to override "defaults" configured here
#
from dotenv import load_dotenv
from urllib.parse import quote
from superset.superset_typing import CacheConfig
import logging
import os
from datetime import timedelta
from typing import Optional
from cachelib.base import BaseCache
from cachelib.file import FileSystemCache
from celery.schedules import crontab
from typing import (
    Any,
    Callable,
    Dict,
    List,
    Literal,
    Optional,
    Set,
    Type,
    TYPE_CHECKING,
    Union,
)

logger = logging.getLogger()

load_dotenv()
from flask import redirect, g, flash, request
from flask_appbuilder.security.views import UserDBModelView,AuthDBView
from superset.security.manager import SupersetSecurityManager
from flask_appbuilder.security.views import expose
from flask_appbuilder.security.manager import BaseSecurityManager
from flask_login import login_user, logout_user

print('**************************************')
class CustomAuthDBView(AuthDBView):
    login_template = 'appbuilder/general/security/login_db.html'

    @expose('/login/', methods=['GET', 'POST'])
    # def login(self):
    #     if request.args.get('username') is not None:
    #         user = self.appbuilder.sm.find_user(username=request.args.get('username'))
    #         flash('Admin auto logged in', 'success')
    #         login_user(user, remember=False)
    #         return redirect(self.appbuilder.get_url_for_index)
    #     elif g.user is not None and g.user.is_authenticated():
    #         return redirect(self.appbuilder.get_url_for_index)
    #     else:
    #         flash('Unable to auto login', 'warning')
    #         return super(CustomAuthDBView,self).login()
    def login(self):
            redirect_url = self.appbuilder.get_url_for_index
            if request.args.get('redirect') is not None:
                redirect_url = request.args.get('redirect') 

            if request.args.get('username') is not None:
                user = self.appbuilder.sm.find_user(username=request.args.get('username'))
                login_user(user, remember=False)
                return redirect(redirect_url)
            elif g.user is not None and g.user.is_authenticated():
                return redirect(redirect_url)
            else:
                flash('Unable to auto login', 'warning')
                return super(CustomAuthDBView,self).login()    

class CustomSecurityManager(SupersetSecurityManager):
    authdbview = CustomAuthDBView
    def __init__(self, appbuilder):
        super(CustomSecurityManager, self).__init__(appbuilder)

def get_env_variable(var_name: str, default: Optional[str] = None) -> str:
    """Get the environment variable or raise exception."""
    try:
        return os.environ[var_name]
    except KeyError:
        if default is not None:
            return default
        else:
            error_msg = "The environment variable {} was missing, abort...".format(
                var_name
            )
            raise EnvironmentError(error_msg)


DATABASE_DIALECT = get_env_variable("DATABASE_DIALECT")
DATABASE_USER = get_env_variable("DATABASE_USER")
DATABASE_PASSWORD = get_env_variable("DATABASE_PASSWORD")
DATABASE_HOST = get_env_variable("DATABASE_HOST")
DATABASE_PORT = get_env_variable("DATABASE_PORT")
DATABASE_DB = get_env_variable("DATABASE_DB")

# DATABASE_PASSWORD = 
# The SQLAlchemy connection string.
# SQLALCHEMY_DATABASE_URI = f'''postgresql://upagadm:{quote(DATABASE_PASSWORD)}@3.7.208.211:1426/superset'''
SQLALCHEMY_DATABASE_URI = "%s://%s:%s@%s:%s/%s" % (
    DATABASE_DIALECT,
    DATABASE_USER,
    DATABASE_PASSWORD,
    DATABASE_HOST,
    DATABASE_PORT,
    DATABASE_DB,
)

REDIS_HOST = get_env_variable("REDIS_HOST")
REDIS_PORT = get_env_variable("REDIS_PORT")
REDIS_CELERY_DB = get_env_variable("REDIS_CELERY_DB", "0")
REDIS_RESULTS_DB = get_env_variable("REDIS_RESULTS_DB", "1")

RESULTS_BACKEND: Optional[BaseCache] = None

CACHE_CONFIG = {
    "CACHE_TYPE": "redis",
    "CACHE_DEFAULT_TIMEOUT": 300,
    "CACHE_KEY_PREFIX": "superset_",
    "CACHE_REDIS_HOST": REDIS_HOST,
    "CACHE_REDIS_PORT": REDIS_PORT,
    "CACHE_REDIS_DB": REDIS_RESULTS_DB,
}
DATA_CACHE_CONFIG = CACHE_CONFIG

FILTER_STATE_CACHE_CONFIG: CacheConfig = {
    "CACHE_DEFAULT_TIMEOUT": int(timedelta(days=90).total_seconds()),
    # should the timeout be reset when retrieving a cached value
    "REFRESH_TIMEOUT_ON_RETRIEVAL": True,
}
THUMBNAIL_CACHE_CONFIG: CacheConfig = {
    "CACHE_TYPE": "NullCache",
    "CACHE_NO_NULL_WARNING": True,
}

EXPLORE_FORM_DATA_CACHE_CONFIG: CacheConfig = {
    "CACHE_DEFAULT_TIMEOUT": int(timedelta(days=7).total_seconds()),
    # should the timeout be reset when retrieving a cached value
    "REFRESH_TIMEOUT_ON_RETRIEVAL": True,
}

# Default cache timeout, applies to all cache backends unless specifically overridden in
# each cache config.
CACHE_DEFAULT_TIMEOUT = int(timedelta(days=1).total_seconds())

# Default cache for Superset objects
CACHE_CONFIG: CacheConfig = {"CACHE_TYPE": "NullCache"}

# Cache for datasource metadata and query results
DATA_CACHE_CONFIG: CacheConfig = {"CACHE_TYPE": "NullCache"}

# store cache keys by datasource UID (via CacheKey) for custom processing/invalidation
STORE_CACHE_KEYS_IN_METADATA_DB = True

class CeleryConfig(object):
    BROKER_URL = f"redis://{REDIS_HOST}:{REDIS_PORT}/{REDIS_CELERY_DB}"
    CELERY_IMPORTS = ("superset.sql_lab",)
    CELERY_RESULT_BACKEND = f"redis://{REDIS_HOST}:{REDIS_PORT}/{REDIS_RESULTS_DB}"
    CELERYD_LOG_LEVEL = "DEBUG"
    CELERYD_PREFETCH_MULTIPLIER = 1
    CELERY_ACKS_LATE = False
    CELERYBEAT_SCHEDULE = {
        "reports.scheduler": {
            "task": "reports.scheduler",
            "schedule": crontab(minute="*", hour="*"),
        },
        "reports.prune_log": {
            "task": "reports.prune_log",
            "schedule": crontab(minute=10, hour=0),
        },
    }


CELERY_CONFIG = CeleryConfig

FEATURE_FLAGS = {"ALERT_REPORTS": True,
"EMBEDDED_SUPERSET": True,
"EMBEDDABLE_CHARTS": True,
"ENABLE_JAVASCRIPT_CONTROLS": True,
"DASHBOARD_CROSS_FILTERS": True,
"DRILL_TO_DETAIL": True,
 "HORIZONTAL_FILTER_BAR": True}
# Embedded config options
GUEST_ROLE_NAME = "Public"
GUEST_TOKEN_JWT_SECRET = "test-guest-secret-change-me"
GUEST_TOKEN_JWT_ALGO = "HS256"
GUEST_TOKEN_HEADER_NAME = "X-GuestToken"
GUEST_TOKEN_JWT_EXP_SECONDS = 300  # 5 minutes
# Guest token audience for the embedded superset, either string or callable
GUEST_TOKEN_JWT_AUDIENCE: Optional[Union[Callable[[], str], str]] = None

ENABLE_CORS = True
CORS_OPTIONS: Dict[Any, Any] = {
  'supports_credentials': True,
  'allow_headers': ['*'],
  'resources': ['*'],
  'origins': ['*']
}
# '/superset/csrf_token/', # auth
# '/superset/explore_json/*', # legacy query API
# '/api/v1/chart/data', # new query API

# ---------------------------------------------------
# List of viz_types not allowed in your environment
# For example: Disable pivot table and treemap:
#  VIZ_TYPE_DENYLIST = ['pivot_table', 'treemap']
# ---------------------------------------------------

#VIZ_TYPE_DENYLIST: List[str] = ['pivot_table', 'treemap']
VIZ_TYPE_DENYLIST = ['pivot_table', 'treemap','world_map']


ALERT_REPORTS_NOTIFICATION_DRY_RUN = True
WEBDRIVER_BASEURL = "http://superset:8088/"
# The base URL for the email report hyperlinks.
WEBDRIVER_BASEURL_USER_FRIENDLY = WEBDRIVER_BASEURL

SQLLAB_CTAS_NO_LIMIT = True
print(os.getcwd())
# from security import CustomSecurityManager
CUSTOM_SECURITY_MANAGER = CustomSecurityManager
#
# Optionally import superset_config_docker.py (which will have been included on
# the PYTHONPATH) in order to allow for local settings to be overridden
#

