
const list = document.getElementById('task-list');
const message = document.getElementById('message');

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: {
      'Content-Type': 'application/json'
    },
    ...options
  });

  const data = await response.json();

  if (!response.ok) {
    throw new Error(data.error || 'Request failed');
  }

  return data;
}

async function loadTasks() {
  try {
    const { tasks } = await api('/api/tasks');

    document.getElementById('total').textContent =
      tasks.length;

    document.getElementById('pending').textContent =
      tasks.filter(t => !t.done).length;

    document.getElementById('completed').textContent =
      tasks.filter(t => t.done).length;

    document.getElementById('count').textContent =
      `${tasks.length} tasks`;

    list.replaceChildren();

    if (!tasks.length) {
      const empty = document.createElement('p');

      empty.className = 'empty';
      empty.textContent =
        'No tasks yet. Add your first task above!';

      list.append(empty);
    }

    for (const task of tasks) {
      const row = document.createElement('div');

      row.className =
        `task ${task.done ? 'done' : ''}`;

      const label = document.createElement('label');

      const check = document.createElement('input');

      check.type = 'checkbox';
      check.checked = task.done;

      check.addEventListener('change', () =>
        run(async () => {
          await api(`/api/tasks/${task.id}`, {
            method: 'PATCH',
            body: JSON.stringify({
              done: check.checked
            })
          });

          await loadTasks();
        })
      );

      const title = document.createElement('span');

      title.className = 'task-title';
      title.textContent = task.title;

      label.append(check, title);

      const del = document.createElement('button');

      del.className = 'delete';
      del.textContent = 'Delete';

      del.setAttribute(
        'aria-label',
        `Delete ${task.title}`
      );

      del.addEventListener('click', () =>
        run(async () => {
          await api(`/api/tasks/${task.id}`, {
            method: 'DELETE'
          });

          await loadTasks();
        })
      );

      row.append(label, del);
      list.append(row);
    }

    message.textContent = '';

  } catch (error) {
    message.textContent = error.message;
  }
}

async function run(action) {
  try {
    await action();
  } catch (error) {
    message.textContent = error.message;
  }
}

document.getElementById('task-form')
  .addEventListener('submit', event => {
    event.preventDefault();

    const input =
      document.getElementById('task-title');

    const title = input.value.trim();

    if (!title) return;

    run(async () => {
      await api('/api/tasks', {
        method: 'POST',
        body: JSON.stringify({ title })
      });

      input.value = '';

      await loadTasks();
    });
  });

loadTasks();

