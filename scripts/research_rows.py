"""Read-only scalar row access for research runs; pandas handles all slices.

Avoid constructing millions of temporary mixed-dtype Series. Strategy rules,
column operations, row order and slice semantics remain unchanged.
"""
import numbers


class Row:
    def __init__(self, columns, index):
        self.columns, self.index = columns, index

    def __getitem__(self, key):
        return self.columns[key][self.index]

    def get(self, key, default=None):
        return self[key] if key in self.columns else default


class ScalarRows:
    def __init__(self, frame):
        self.frame = frame
        self.columns = {name: frame[name].to_numpy(dtype=object)
                        if name == 'datetime' else frame[name].to_numpy()
                        for name in frame.columns}

    def __getitem__(self, key):
        if isinstance(key, numbers.Integral):
            return Row(self.columns, key)
        return self.frame.iloc[key]


class ResearchFrame:
    def __init__(self, frame):
        self.frame = frame
        self.iloc = ScalarRows(frame)

    def __getitem__(self, key):
        return self.frame[key]

    def __getattr__(self, key):
        return getattr(self.frame, key)

    def __len__(self):
        return len(self.frame)


def accelerate_research(generator):
    cache = {}
    for model in generator.models:
        generate = model.generate

        def wrapped(frame, daily, context, method=generate):
            if cache.get('source') is not frame:
                cache['source'] = frame
                cache['view'] = ResearchFrame(frame)
            print(f'  scanning {method.__self__.name}', flush=True)
            return method(cache['view'], daily, context)

        model.generate = wrapped
    return generator
