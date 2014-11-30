
import pkgutil
import traceback
import re
from os import path

__all__ = [] # No modules should be accessed statically
__running = {}


class PluginOptions(dict):
    def __init__(self, plugin, defaults):
        super(PluginOptions, self).__init__(defaults.iteritems())

        from options import options
        if plugin in options:
            for key, value in options[plugin].iteritems():
                if key in self:
                    value_type = type(value)
                    if value_type == unicode:
                        value_type = str
                    default_type = type(self[key])
                    if default_type == unicode:
                        default_type = str

                    if value_type == default_type:
                        self[key] = value

        self._plugin = plugin

    def __setitem__(self, key, value):
        try:
            super(PluginOptions, self).__setitem__(key, value)
            if hasattr(self, '_plugin'):
                from options import options
                options[self._plugin] = self.copy()
        except ValueError:  # No index available yet
            pass

    def web_update(self, qdict, skipped=None):
        for key in self.keys():
            if skipped is not None and key in skipped:
                continue
            old_value = self[key]
            if isinstance(old_value, bool):
                self[key] = True if qdict.get(key, 'off') == 'on' else False
            elif isinstance(old_value, int):
                self[key] = int(qdict.get(key, old_value))
            elif isinstance(old_value, float):
                self[key] = float(qdict.get(key, old_value))
            elif isinstance(old_value, str) or isinstance(old_value, unicode):
                self[key] = qdict.get(key, old_value)


def available():
    plugins = []
    for imp, module, is_pkg in pkgutil.iter_modules(['plugins']):
        if plugin_name(module) is not None:
            plugins.append(module)
    return plugins


def plugin_name(plugin):
    """Tries to find the name of the given plugin without importing it yet."""
    filename = path.join(path.dirname(__file__), plugin + '.py')
    try:
        with open(filename) as fh:
            for line in fh:
                if 'NAME' in line:
                    match = re.search('NAME\\s=\\s("|\')([^"\']+)("|\')', line)
                    if match is not None:
                        return match.group(2)
    except Exception:
        pass
    return None


def plugin_names():
    return {plugin: (plugin_name(plugin)) for plugin in available() if plugin_name(plugin)}


def plugin_url(cls):
    from webpages import WebPage
    import inspect
    if cls is None:
        result = cls
    else:
        if inspect.isclass(cls) and issubclass(cls, WebPage):
            cls = cls.__module__ + '.' + cls.__name__

        parts = cls.split('.')
        if len(parts) >= 3:
            result = '/p/' + '/'.join(parts[1:])
        elif len(parts) >= 2:
            result = '/p/' + '/'.join(parts)
        else:
            result = '/p/' + cls

        if result.endswith('_page'):
            result = result[:-5]

        if result.endswith('_json'):
            result = result[:-5] + '.json'

    return result


def _get_urls(import_name, plugin):
    from webpages import WebPage
    import inspect

    result = []
    for element in dir(plugin):
        if inspect.isclass(getattr(plugin, element)) and issubclass(getattr(plugin, element), WebPage):
            if import_name == getattr(plugin, element).__module__:
                classname = import_name + '.' + element
                result.append(plugin_url(classname))
                result.append(classname)

    return result


def start_enabled_plugins():
    from options import options
    import logging
    from urls import urls
    for module in available():
        if module in options.enabled_plugins and module not in __running:
            plugin_name = module
            import_name = __name__ + '.' + module
            try:
                plugin = getattr(__import__(import_name), module)
                plugin_name = plugin.NAME
                if plugin.LINK is not None and not (plugin.LINK.startswith(module) or plugin.LINK.startswith(__name__)):
                    plugin.LINK = module + '.' + plugin.LINK
                plugin_urls = _get_urls(import_name, plugin)
                urls += plugin_urls
                __running[module] = plugin
                plugin.start()
                logging.info('Started the {} plug-in.'.format(plugin_name))
            except Exception as e:
                logging.info('Failed to load the {} plug-in:'.format(plugin_name))
                traceback.print_exc()
                options.enabled_plugins.remove(module)

    for module, plugin in __running.copy().iteritems():
        if module not in options.enabled_plugins:
            import_name = __name__+'.'+module
            plugin_name = plugin.NAME
            plugin_urls = _get_urls(import_name, plugin)
            try:
                for url in plugin_urls:
                    if url in urls:
                        urls.remove(url)
                plugin.stop()
                del __running[module]
                logging.info('Stopped the {} plug-in.'.format(plugin_name))
            except Exception as e:
                logging.info('Failed to stop the {} plug-in:'.format(plugin_name))
                traceback.print_exc()


def running():
    return __running.keys()


def get(name):
    return __running[name]