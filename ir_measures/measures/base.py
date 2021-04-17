import itertools
import ir_measures


class BaseMeasure:
    NAME = None
    AT_PARAM = 'cutoff' # allows measures to configure which param measure@X updates (default is cutoff)
    SUPPORTED_PARAMS = {}

    def __init__(self, **params):
        self.params = params
        self.validated = False

    def validate_params(self):
        if self.validated:
            return
        assert isinstance(self.params, dict), "params must be dict"
        unsupposed_params = list(self.params.keys() - self.SUPPORTED_PARAMS.keys())
        assert len(unsupposed_params) == 0, f"unsupported params found: {unsupposed_params}"
        for param_name, param in self.SUPPORTED_PARAMS.items():
            param_val = self.params.get(param_name, _NOT_PROVIDED)
            is_valid = param.validate(param_val)
            assert is_valid, f"invalid param {param_name}={repr(param_val)}"
        self.validated = True

    def __call__(self, **kwargs):
        product = []
        for k, v in kwargs.items():
            if isinstance(v, (list, tuple)):
                product.append([(k, item) for item in v])
        results = []
        for items in itertools.product(*product):
            params = dict(self.params)
            params.update(kwargs)
            params.update(items)
            results.append(type(self)(**params))
        if product:
            result = MultiMeasures(*results)
            return result
        return results[0]

    def __matmul__(self, at_param):
        return self(**{self.AT_PARAM: at_param})

    def __getitem__(self, key):
        default = self.SUPPORTED_PARAMS[key].default
        return self.params.get(key, default)

    def iter_calc(self, qrels, run):
        self.validate_params()
        return ir_measures.iter_calc([self], qrels, run)

    def calc_aggregate(self, qrels, run):
        return ir_measures.calc_aggregate([self], qrels, run)[self]

    @classmethod
    def aggregate(cls, calc_iter):
        result = 0.
        count = 0
        for metric in calc_iter:
            if metric.measure is self:
                result += metric.value
                count += 1
        return result / count

    def __str__(self):
        return repr(self)

    def __repr__(self):
        result = self.NAME
        params = ', '.join(f'{k}={repr(v)}' for k, v in self.params.items() if k != self.AT_PARAM and v != self.SUPPORTED_PARAMS[k].default)
        if params:
            result = f'{result}({params})'
        if self.AT_PARAM in self.params:
            result = f'{result}@{self.params[self.AT_PARAM]}'
        return result

    def __eq__(self, other):
        if isinstance(other, BaseMeasure):
            return repr(self) == repr(other)
        return False

    def __hash__(self):
        return hash(repr(self))


class MultiMeasures:
    def __init__(self, *measures):
        self.measures = set()
        self._add_measures(measures)

    def _add_measures(self, measures):
        for m in measures:
            if isinstance(m, MultiMeasures):
                self._add_measures(m.measures)
            else:
                self.measures.add(m)

    def __call__(self, **kwargs):
        return MultiMeasures(*(m(**kwargs) for m in self.measures))

    def __matmul__(self, at_param):
        return MultiMeasures(*(m(**{m.AT_PARAM: at_param}) for m in self.measures))

    def __str__(self):
        return repr(self)

    def __repr__(self):
        if self.measures:
            return f'MultiMeasures({repr(self.measures)[1:-1]})'
        return 'MultiMeasures()'

    def iter_calc(self, qrels, run):
        return ir_measures.DefaultPipeline.iter_calc(self.measures, qrels, run)

    def calc_aggregate(self, qrels, run):
        return self.aggregate(self.iter_calc())


_NOT_PROVIDED = object()


class ParamInfo:
    def __init__(self, dtype=None, required=False, choices=_NOT_PROVIDED, default=_NOT_PROVIDED, desc=None):
        self.dtype = dtype
        self.required = required
        self.choices = choices
        self.default = default
        self.desc = desc

    def validate(self, value):
        if value is _NOT_PROVIDED:
            return not self.required
        if self.dtype is not None and not isinstance(value, self.dtype):
            return False
        if self.choices is not _NOT_PROVIDED and value not in self.choices:
            return False
        return True
