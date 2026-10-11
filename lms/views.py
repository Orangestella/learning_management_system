"""Table presentation metadata. Templates only render cells and actions."""
from urllib.parse import urlencode
from flask import render_template
from .search import search_metadata

HEADERS = {
    'account': ['ID', 'First name', 'Last name', 'Role'],
    'course': ['ID', 'Name', 'Lead instructor', 'Instructor ID', 'Session'],
    'assignment': ['ID', 'Name', 'Course', 'Deadline'],
    'forum': ['ID', 'Name'], 'membership': ['ID', 'First name', 'Last name', 'Student ID'],
    'messages': ['ID', 'Sender', 'Content', 'Sent'],
    'enrollment requests': ['ID', 'Student', 'Student ID', 'Course', 'Session'],
    'student': ['ID', 'First name', 'Last name'],
    'submission': ['ID', 'Student', 'Submitted', 'Attachment'],
    'enroll': ['ID', 'Course', 'Session', 'Lead instructor'], 'join forum': ['ID', 'Name'],
}


def action(label, path, method='GET'):
    return dict(label=label, url=path, method=method)


def admin_actions(kind, identifier):
    query = '?' + urlencode({'id': identifier})
    if kind == 'enrollment requests':
        return [action('Approve', '/course/enroll/receive' + query, 'POST'), action('Deny', '/course/enroll/deny' + query, 'POST')]
    # Membership editing was never implemented; expose only functioning operations.
    if kind == 'membership':
        return []
    result = [action('Delete', f'/{kind}/delete' + query, 'POST')]
    if kind != 'messages': result.append(action('Edit', f'/{kind}/edit' + query))
    if kind == 'forum': result.append(action('Members', f'/forum/membership/{identifier}'))
    return result


def student_actions(kind, identifier):
    paths = {'enroll': ('Enroll', '/enroll/request/send', 'POST'),
             'join forum': ('Join', '/forum/stu/join', 'POST'),
             'notification': ('View', '/notification/view', 'GET'),
             'messages': ('Delete', '/messages/delete', 'POST')}
    if kind not in paths: return []
    label, path, method = paths[kind]
    return [action(label, path + '?' + urlencode({'id': identifier}), method)]


def instructor_actions(kind, identifier):
    if kind == 'student': return []
    query = '?' + urlencode({'id': identifier})
    if kind == 'submission': return [action('Evaluate', '/submission/eval' + query)]
    if kind == 'messages': return [action('Delete', '/messages/delete' + query, 'POST')]
    result = [action('Edit', f'/{kind}/edit' + query), action('Delete', f'/{kind}/delete' + query, 'POST')]
    if kind == 'notification': result.insert(0, action('View', '/notification/view' + query))
    return result


def render(template, **context):
    table_templates = {'console.html': ('adminbase.html', admin_actions),
                       'ins_table.html': ('ins_base.html', instructor_actions),
                       'non_admin_table.html': ('student_base.html', student_actions)}
    if template not in table_templates:
        return render_template(template, **context)
    base, build_actions = table_templates[template]
    kind = context['type']
    if kind == 'messages':
        return render_template('messages.html', base_template=base, search=search_metadata(kind), **context)
    headers = HEADERS.get(kind, [])
    file_column = None
    if kind == 'lecture':
        headers = ['ID', 'Name']
        if template == 'console.html' or (template == 'ins_table.html' and not context.get('edit')):
            headers += ['Course']
        file_column = len(headers)
        headers += ['Resource']
        if template != 'console.html': headers += ['Description', 'Uploaded']
    elif kind == 'notification':
        headers = ['ID', 'Title', 'Sent'] if template == 'ins_table.html' else ['ID', 'Sender', 'Title', 'Sent']
    elif kind == 'submission': file_column = 3
    rows = []
    for item in context.get('items', []):
        cells = []
        for index, value in enumerate(item):
            url = value if index == file_column and isinstance(value, str) and value.startswith('/files/') else None
            cells.append(dict(value=value, url=url))
        rows.append(dict(cells=cells, actions=build_actions(kind, item[0])))
    toolbar = []
    if kind == 'messages':
        toolbar.append(action('Write message', '/messages/create'))
    if template == 'console.html' and kind not in ('membership', 'enrollment requests', 'messages'):
        toolbar.append(action('Create', f'/{kind}/create'))
    if template == 'console.html' and kind == 'course':
        toolbar.append(action('Enrollment requests', '/course/enroll/request'))
    if template == 'ins_table.html' and context.get('edit') and kind in ('lecture', 'notification'):
        toolbar.append(action('Create', f'/{kind}/create?' + urlencode({'id': context.get('crs_id', '')})))
    context.update(table=dict(headers=headers, rows=rows, toolbar=toolbar), base_template=base, search=search_metadata(kind))
    page = 'forum_directory.html' if kind in ('forum', 'join forum') else 'table.html'
    return render_template(page, **context)
