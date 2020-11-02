try:
    # imported to verify django's available
    from django.db import models
except ModuleNotFoundError:
    import sys
    sys.exit('Django required')

# Create your models here.
