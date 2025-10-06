# coding=utf-8
"""
    一些实用的工具类将逐渐转移到这里。
"""
import inspect
import functools
import BigWorld


def override(obj, prop, getter=None, setter=None, deleter=None):
    """
        覆盖对象中的属性，Attribute应当为属性或可调用对象。
        getter、setter 和 deleter 应该是可调用的或为 None
        :param obj: object，填入需要覆盖的属性
        :param prop: 对象中任何属性的名称（可以不进行混淆）
        :param getter: Getter function
        :param setter: Setter function
        :param deleter: Deleter function
    """
    if inspect.isclass(obj) and prop.startswith('__') and prop not in dir(obj) + dir(type(obj)):
        prop = obj.__name__ + prop
        if not prop.startswith('_'):
            prop = '_' + prop

    src = getattr(obj, prop)
    if type(src) is property and (getter or setter or deleter):
        assert getter is None or callable(getter), 'Getter is not callable!'
        assert setter is None or callable(setter), 'Setter is not callable!'
        assert deleter is None or callable(deleter), 'Deleter is not callable!'

        getter = functools.partial(getter, src.fget) if getter else src.fget
        setter = functools.partial(setter, src.fset) if setter else src.fset
        deleter = functools.partial(deleter, src.fdel) if deleter else src.fdel

        setattr(obj, prop, property(getter, setter, deleter))
        return getter
    elif getter:
        assert callable(src), 'Source property is not callable!'
        assert callable(getter), 'Handler is not callable!'

        if inspect.isclass(obj) and inspect.ismethod(src) \
                or isinstance(src, type(BigWorld.Entity.__getattribute__)):
            getter_new = lambda *args, **kwargs: getter(src, *args, **kwargs)
        else:
            getter_new = functools.partial(getter, src)

        setattr(obj, prop, getter_new)
        return getter
    else:
        return functools.partial(override, obj, prop)
