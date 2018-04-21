# This is here simply to aid migration to trefoil.  It will be removed in a future version!

import sys
import warnings

import trefoil

warnings.simplefilter('always', DeprecationWarning)
warnings.warn(
    "the package name 'clover' has been deprecated; use 'trefoil' instead",
    DeprecationWarning)

sys.modules['clover'] = trefoil