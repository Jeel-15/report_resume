from mongoengine import connect
connect('database.db')
from models.degree import Degree
from models.department import Department

def obj_id(doc):
    if doc is None:
        return None
    if isinstance(doc, dict):
        return str(doc.get('_id') or doc.get('id')) if (doc.get('_id') or doc.get('id')) else None
    if isinstance(doc, (str, int)):
        return str(doc)
    direct = getattr(doc, 'id', None)
    if direct is not None:
        return str(direct)
    raw = getattr(doc, '_data', {}) or {}
    raw_id = raw.get('id')
    return str(raw_id) if raw_id is not None else None

print('Degrees:')
for deg in Degree.objects():
    print('-', obj_id(deg), repr(getattr(deg, 'name', '')))

print('\nDepartments:')
for dep in Department.objects():
    degree_attr = getattr(dep, 'degree', None)
    print('DEP', obj_id(dep), repr(getattr(dep,'name','')))
    print('  degree_attr_type=', type(degree_attr).__name__, 'degree_attr=', degree_attr)
    print('  _data.degree =', (getattr(dep,'_data',{}) or {}).get('degree'))
