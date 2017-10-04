from __future__ import absolute_import, division, print_function, unicode_literals


#===================================================================================================
# SkypeMessage
#===================================================================================================
class SkypeMessage(object):


    @staticmethod
    def link(url, display=None):
        """
        Create a hyperlink.  If ``display`` is not specified, display the URL.
        .. note:: Anomalous API behaviour: official clients don't provide the ability to set display text.
        Args:
            url (str): full URL to link to
            display (str): custom label for the hyperlink
        Returns:
            str: tag to display a hyperlink
        """
        return """<a href="{0}">{1}</a>""".format(url, display or url)
