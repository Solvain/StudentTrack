import { ApiError, clearToken, formatScore, request } from './api.mjs';

const byId = (id) => document.getElementById(id);
const selectionKey = 'studenttrack.semester';
const modeLabels = { subject_means: 'Середній бал за предметами', all_grades: 'Середній бал за всіма оцінками' };
const scales = [5, 12, 100].map((value) => [value, `${value} балів`]);
const numberWords = new Intl.PluralRules('uk-UA');
const state = {
  ready: false,
  loading: false,
  student: null,
  semesters: [],
  semester: null,
  subjects: [],
  statistics: null,
  progress: null,
  openSubjects: new Set(),
  grades: new Map(),
  loadingGrades: new Set(),
  gradeErrors: new Map(),
  remaining: new Map(),
  forecast: null,
  forecastError: '',
  forecasting: false,
  forecastRevision: 0,
};

function element(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

function button(className, text, action, accessibleName) {
  const node = element('button', className, text);
  node.type = 'button';
  node.addEventListener('click', action);
  if (accessibleName) {
    node.setAttribute('aria-label', accessibleName);
    node.title = accessibleName;
  }
  return node;
}

function setNotice(node, message) {
  node.textContent = message;
  node.hidden = !message;
}

function countGrades(count) {
  const noun = { one: 'оцінка', few: 'оцінки', many: 'оцінок', other: 'оцінки' };
  return `${count} ${noun[numberWords.select(count)]}`;
}

function apiMessage(error, { invalid, conflict } = {}) {
  if (!(error instanceof ApiError)) return 'Не вдалося зв’язатися із сервером. Спробуйте ще раз.';
  if (error.status === 404) return 'Запис більше недоступний. Оновіть список.';
  if (error.status === 409) return conflict ?? 'Зміна суперечить поточним даним.';
  if (error.status === 422) return invalid ?? 'Перевірте, чи правильно заповнено поля.';
  return 'Сервер не зміг виконати запит. Спробуйте ще раз.';
}

function rememberSemester(id) {
  try {
    if (id == null) localStorage.removeItem(selectionKey);
    else localStorage.setItem(selectionKey, String(id));
  } catch {
    // The semester selector works even without browser storage.
  }
}

function rememberedSemester() {
  try {
    return localStorage.getItem(selectionKey);
  } catch {
    return null;
  }
}

function clearForecast() {
  state.forecast = null;
  state.forecastError = '';
  state.forecasting = false;
  state.forecastRevision += 1;
}

async function reload(preferredSemester = state.semester?.id ?? rememberedSemester()) {
  if (state.loading) return;
  state.loading = true;
  byId('load-error').hidden = true;
  renderControls();
  try {
    const student = await request('/students/me');
    const semesters = student ? await request('/semesters') : [];
    const semester = semesters.find(({ id }) => String(id) === String(preferredSemester)) ?? semesters[0] ?? null;
    const [subjects, statistics, progress] = semester ? await Promise.all([
      request(`/subjects?semester_id=${semester.id}`),
      request(`/statistics?semester_id=${semester.id}`),
      request(`/scholarship/progress?semester_id=${semester.id}`),
    ]) : [[], null, null];

    if (state.semester?.id !== semester?.id) {
      state.openSubjects.clear();
      state.remaining.clear();
    }
    for (const subjectId of state.openSubjects) {
      if (!subjects.some(({ id }) => id === subjectId)) state.openSubjects.delete(subjectId);
    }
    for (const subjectId of state.remaining.keys()) {
      if (!subjects.some(({ id }) => id === subjectId)) state.remaining.delete(subjectId);
    }
    state.grades.clear();
    state.gradeErrors.clear();
    state.loadingGrades = new Set();
    clearForecast();
    Object.assign(state, { student, semesters, semester, subjects, statistics, progress, ready: true });
    rememberSemester(semester?.id);
    for (const subjectId of state.openSubjects) void loadGrades(subjectId);
  } catch (error) {
    byId('load-error-text').textContent = apiMessage(error);
    byId('load-error').hidden = false;
  } finally {
    state.loading = false;
    render();
  }
}

function renderControls() {
  const { ready, loading, student, semesters, semester } = state;
  byId('profile-button').disabled = !ready || loading;
  byId('new-term').disabled = loading || !student;
  byId('term-select').disabled = loading || !semesters.length;
  byId('term-settings').disabled = loading || !semester;
  byId('new-subject').disabled = loading || !semester;
  byId('goal-button').disabled = loading || !semester;
  byId('setup-action').disabled = loading;
}

function render() {
  const { ready, student, semesters, semester } = state;
  const profileName = student?.display_name ?? 'Профіль';
  const avatar = student ? profileName.trim().split(/\s+/).slice(0, 2).map((part) => [...part][0]).join('') : 'СТ';
  byId('profile-initials').textContent = avatar.toLocaleUpperCase('ru');
  byId('profile-name').textContent = profileName;
  byId('profile-caption').textContent = student ? 'Налаштування профілю' : 'Створити профіль';

  const select = byId('term-select');
  select.replaceChildren(...semesters.map(({ id, name }) => new Option(name, id)));
  if (semester) select.value = semester.id;
  else select.append(new Option('Семестр не вибрано', ''));

  byId('page-intro').textContent = semester
    ? `${semester.name} · ${semester.grading_scale}-бальна шкала`
    : 'Оцінки й навчальна ціль для кожного семестру';
  byId('setup-banner').hidden = !ready || Boolean(semester);
  byId('setup-heading').textContent = student ? 'Створіть перший семестр' : 'Створіть профіль';
  byId('setup-description').textContent = student
    ? 'Виберіть шкалу оцінювання й спосіб розрахунку середнього бала.'
    : 'Вкажіть ім’я, щоб почати відстежувати успішність.';
  byId('setup-action').textContent = student ? 'Створити семестр' : 'Створити профіль';

  renderControls();
  renderSummary();
  renderSubjects();
  renderForecast();
}

function renderSummary() {
  const { semester, subjects, statistics, progress } = state;
  const scaleLabel = semester ? `/ ${semester.grading_scale}` : '';
  byId('average').textContent = formatScore(statistics?.overall_average);
  byId('average-scale').textContent = scaleLabel;
  byId('average-note').textContent = semester ? modeLabels[semester.averaging_mode] : 'З’явиться після першої оцінки';
  byId('summary-subjects').textContent = `Предмети · ${semester ? subjects.length : '—'}`;
  byId('summary-grades').textContent = `Оцінки · ${statistics?.grade_count ?? '—'}`;

  const target = progress?.target_average ?? null;
  const currentProgress = progress?.progress_percent ?? null;
  byId('goal-score').textContent = formatScore(target);
  byId('goal-scale').textContent = scaleLabel;
  byId('goal-button').textContent = target === null ? 'Встановити ціль' : 'Змінити';
  byId('goal-button').setAttribute('aria-label', target === null ? 'Встановити ціль' : 'Змінити ціль');
  const belowTargetAfterRounding = currentProgress === 100 && progress?.goal_reached === false;
  const progressCaption = belowTargetAfterRounding ? '< 100 %' : `${formatScore(currentProgress)} %`;
  byId('progress-caption').textContent = currentProgress === null ? '—' : progressCaption;
  const progressBar = byId('goal-progress');
  progressBar.value = belowTargetAfterRounding ? 99.9 : Number(currentProgress ?? 0);
  progressBar.setAttribute('aria-valuetext', currentProgress === null ? 'Даних поки немає' : progressCaption);
  byId('goal-note').textContent = target === null ? 'Встановіть ціль на цей семестр'
    : currentProgress === null ? 'Поступ буде видно після першої оцінки'
      : progress.goal_reached ? 'Навчальної цілі досягнуто' : 'Навчальної цілі ще не досягнуто';
}

function renderSubjects() {
  const { semester, subjects, statistics } = state;
  const stats = new Map((statistics?.subjects ?? []).map((subject) => [subject.id, subject]));
  const list = byId('subject-list');
  const activeToggle = document.activeElement?.dataset.subjectToggle;
  list.hidden = subjects.length === 0;
  byId('subjects-empty').hidden = subjects.length > 0;
  byId('subjects-empty-text').textContent = semester
    ? 'Додайте перший предмет, щоб почати записувати оцінки.'
    : 'Створіть або виберіть семестр, щоб вести список предметів.';
  list.replaceChildren(...subjects.map((subject) => subjectRow(subject, stats.get(subject.id))));
  if (activeToggle) list.querySelector(`[data-subject-toggle="${activeToggle}"]`)?.focus({ preventScroll: true });
}

function subjectRow(subject, stats) {
  const open = state.openSubjects.has(subject.id);
  const item = element('li', 'subject-item');
  const row = element('div', 'subject-main');
  const toggle = button('subject-toggle', '', () => toggleSubject(subject.id));
  toggle.dataset.subjectToggle = subject.id;
  toggle.setAttribute('aria-expanded', String(open));
  toggle.setAttribute('aria-controls', `subject-details-${subject.id}`);
  const icon = element('span', 'subject-icon', [...subject.name.trim()][0]?.toLocaleUpperCase('ru') ?? '•');
  icon.setAttribute('aria-hidden', 'true');
  const name = element('span', 'subject-name');
  name.append(element('strong', '', subject.name), element('span', 'subject-metadata', countGrades(stats?.grade_count ?? 0)));
  toggle.append(icon, name);

  const score = element('span', 'subject-score', formatScore(stats?.average));
  score.title = 'Середній бал з предмета';
  const actions = element('div', 'subject-actions');
  actions.append(button('icon-button subject-edit', '⋯', () => editSubject(subject), `Змінити предмет ${subject.name}`));
  row.append(toggle, score, actions);

  const details = element('div', 'subject-details');
  details.id = `subject-details-${subject.id}`;
  details.hidden = !open;
  if (open) renderSubjectDetails(details, subject);
  item.append(row, details);
  return item;
}

function renderSubjectDetails(details, subject) {
  const grades = state.grades.get(subject.id);
  const error = state.gradeErrors.get(subject.id);
  if (error) {
    details.append(element('p', 'form-error', error));
    details.append(button('button button-secondary', 'Повторити', () => loadGrades(subject.id)));
  } else if (!grades) {
    details.append(element('p', 'form-hint', 'Завантаження оцінок…'));
  } else if (grades.length === 0) {
    details.append(element('p', 'form-hint', 'Оцінок поки немає.'));
  } else {
    const list = element('ul', 'grade-list');
    for (const grade of grades) {
      const item = element('li');
      item.append(button('grade-pill', grade.value, () => editGrade(subject, grade), `Змінити оцінку ${grade.value}`));
      list.append(item);
    }
    details.append(list);
  }
  const actions = element('div', 'grade-actions');
  actions.append(button('button button-secondary', '+ Оцінка', () => editGrade(subject), `Додати оцінку · ${subject.name}`));
  details.append(actions);
}

function toggleSubject(id) {
  if (state.openSubjects.has(id)) {
    state.openSubjects.delete(id);
    renderSubjects();
  } else {
    state.openSubjects.add(id);
    if (state.grades.has(id)) renderSubjects();
    else void loadGrades(id);
  }
}

async function loadGrades(id) {
  const pending = state.loadingGrades;
  if (pending.has(id)) return;
  pending.add(id);
  state.gradeErrors.delete(id);
  renderSubjects();
  try {
    const grades = await request(`/grades?subject_id=${id}`);
    if (pending === state.loadingGrades) state.grades.set(id, grades);
  } catch (error) {
    if (pending === state.loadingGrades) state.gradeErrors.set(id, apiMessage(error));
  } finally {
    pending.delete(id);
    if (pending === state.loadingGrades) renderSubjects();
  }
}

function renderForecast() {
  const { semester, subjects, progress, remaining } = state;
  const target = progress?.target_average ?? null;
  const available = Boolean(semester && target !== null && subjects.length);
  byId('forecast-form').hidden = !available;
  byId('forecast-empty').hidden = available;
  byId('forecast-empty-text').textContent = !semester ? 'Прогноз доступний після налаштування семестру.'
    : target === null ? 'Встановіть ціль для стипендії, щоб розрахувати прогноз.'
      : 'Додайте предмети, з яких ще потрібно виконати роботи.';

  const fields = byId('forecast-fields');
  fields.replaceChildren(...subjects.map((subject) => {
    const label = element('label', 'forecast-field');
    const input = element('input');
    input.type = 'number';
    input.min = '0';
    input.max = String(Number.MAX_SAFE_INTEGER);
    input.step = '1';
    input.inputMode = 'numeric';
    input.placeholder = '0';
    input.value = remaining.get(subject.id) ?? '';
    input.addEventListener('input', () => {
      state.remaining.set(subject.id, input.value);
      clearForecast();
      renderForecastResult();
    });
    label.append(element('span', '', subject.name), input);
    return label;
  }));
  renderForecastResult();
}

function renderForecastResult() {
  const { forecast, forecastError, forecasting } = state;
  setNotice(byId('forecast-error'), forecastError);
  byId('forecast-plan').disabled = forecasting;
  byId('forecast-submit').textContent = forecasting ? 'Розрахунок…' : 'Розрахувати прогноз';
  const result = byId('forecast-result');
  result.hidden = !forecast;
  if (!forecast) return;

  result.classList.toggle('is-unreachable', !forecast.possible);
  if (forecast.possible) {
    result.replaceChildren(
      element('span', 'forecast-result-label', 'Оцінка за кожну роботу'),
      element('strong', 'forecast-result-value', forecast.minimum_uniform_grade),
      element('p', '', `Прогнозований середній бал · ${formatScore(forecast.projected_average)}`),
    );
  } else {
    result.replaceChildren(
      element('strong', '', 'За цим планом цілі досягти неможливо'),
      element('p', '', `Максимальний середній бал · ${formatScore(forecast.best_possible_average)}`),
    );
  }
}

async function calculateForecast(event) {
  event.preventDefault();
  if (state.forecasting || !state.semester) return;
  const remaining = Object.fromEntries([...state.remaining].flatMap(([id, raw]) => {
    const count = Number(raw);
    return count > 0 && Number.isSafeInteger(count) ? [[id, count]] : [];
  }));
  clearForecast();
  if (Object.keys(remaining).length === 0) {
    state.forecastError = 'Вкажіть кількість робіт, які ще потрібно виконати, хоча б з одного предмета.';
    renderForecastResult();
    return;
  }
  const revision = state.forecastRevision;
  state.forecasting = true;
  renderForecastResult();
  try {
    const forecast = await request('/scholarship/forecast', {
      method: 'POST', data: { semester_id: state.semester.id, remaining_by_subject: remaining },
    });
    if (revision === state.forecastRevision) state.forecast = forecast;
  } catch (error) {
    if (revision === state.forecastRevision) {
      state.forecastError = apiMessage(error, { invalid: 'Перевірте кількість робіт, які ще потрібно виконати з кожного предмета.' });
    }
  } finally {
    if (revision === state.forecastRevision) {
      state.forecasting = false;
      renderForecastResult();
    }
  }
}

const editor = byId('editor');
const confirmDialog = byId('confirm-dialog');
let editOperation;
let confirmationOperation;
let toastTimeout;

function formField({ name, label, value, type = 'text', options, ...attributes }) {
  const wrapper = element('label', 'form-field');
  const input = element(options ? 'select' : 'input');
  if (options) input.replaceChildren(...options.map(([key, text]) => new Option(text, key)));
  else input.type = type;
  input.name = name;
  input.value = value ?? '';
  input.required = true;
  for (const [key, attribute] of Object.entries(attributes)) input.setAttribute(key, attribute);
  wrapper.append(element('span', '', label), input);
  return wrapper;
}

function showEditor(operation) {
  if (state.loading || editor.open) return;
  editOperation = operation;
  byId('editor-title').textContent = operation.title;
  const body = byId('editor-body');
  const fields = operation.fields.map(formField);
  body.replaceChildren(...fields);
  if (operation.hint) body.append(element('p', 'form-hint', operation.hint));
  byId('editor-delete').hidden = !operation.remove;
  byId('editor-delete').textContent = operation.remove?.label ?? 'Видалити';
  byId('editor-save').textContent = operation.saveLabel ?? 'Зберегти';
  setNotice(byId('editor-error'), '');
  editor.showModal();
  fields[0]?.querySelector('input, select')?.focus();
}

function showConfirmation(operation) {
  confirmationOperation = operation;
  byId('confirm-title').textContent = operation.title;
  byId('confirm-body').textContent = operation.message;
  setNotice(byId('confirm-error'), '');
  confirmDialog.showModal();
}

function setDialogBusy(dialog, busy) {
  if (busy) dialog.setAttribute('aria-busy', 'true');
  else dialog.removeAttribute('aria-busy');
  for (const field of dialog.querySelectorAll('button, input, select')) field.disabled = busy;
}

function toast(message) {
  clearTimeout(toastTimeout);
  const node = byId('toast');
  setNotice(node, message);
  toastTimeout = setTimeout(() => setNotice(node, ''), 3200);
}

async function afterMutation(label, preferredSemester) {
  if (confirmDialog.open) confirmDialog.close();
  if (editor.open) editor.close();
  await reload(preferredSemester);
  toast(label);
}

function editProfile() {
  const student = state.student;
  if (!student) { window.location.replace('/login'); return; }
  showEditor({
    title: student ? 'Налаштування профілю' : 'Створити профіль',
    fields: [{ name: 'display_name', label: 'Ім’я', value: student?.display_name, maxlength: 120, autocomplete: 'name' }],
    saveLabel: student ? 'Зберегти' : 'Створити профіль',
    save: (data) => request(student ? '/students/me' : '/students', {
      method: student ? 'PATCH' : 'POST', data: { display_name: data.display_name.trim() },
    }),
    success: student ? 'Профіль оновлено' : 'Профіль створено',
    conflict: 'Профіль уже існує. Оновіть сторінку.',
    remove: student ? {
      label: 'Видалити профіль', title: 'Видалити профіль?',
      message: 'Усі семестри, предмети, оцінки й цілі буде видалено.',
      path: '/students/me', success: 'Профіль видалено',
    } : null,
  });
}

function editSemester(semester) {
  showEditor({
    title: semester ? 'Налаштування семестру' : 'Новий семестр',
    fields: [
      { name: 'name', label: 'Назва', value: semester?.name, maxlength: 120, placeholder: 'Наприклад, осінь 2026' },
      { name: 'grading_scale', label: 'Шкала оцінювання', value: semester?.grading_scale ?? 5, options: scales },
      { name: 'averaging_mode', label: 'Спосіб розрахунку середнього бала', value: semester?.averaging_mode ?? 'subject_means', options: Object.entries(modeLabels) },
    ],
    saveLabel: semester ? 'Зберегти' : 'Створити семестр',
    save: (data) => request(semester ? `/semesters/${semester.id}` : '/semesters', {
      method: semester ? 'PATCH' : 'POST',
      data: { name: data.name.trim(), grading_scale: Number(data.grading_scale), averaging_mode: data.averaging_mode },
    }),
    preferredSemester: (result) => result.id,
    success: semester ? 'Семестр оновлено' : 'Семестр створено',
    conflict: 'Перш ніж змінити шкалу, видаліть оцінки й ціль цього семестру.',
    remove: semester ? {
      label: 'Видалити семестр', title: 'Видалити семестр?',
      message: 'Усі предмети, оцінки й навчальну ціль цього семестру буде видалено.',
      path: `/semesters/${semester.id}`, success: 'Семестр видалено',
    } : null,
  });
}

function editSubject(subject) {
  if (!state.semester) return;
  const semesterId = state.semester.id;
  showEditor({
    title: subject ? 'Змінити предмет' : 'Новий предмет',
    fields: [{ name: 'name', label: 'Назва', value: subject?.name, maxlength: 120, placeholder: 'Наприклад, математика' }],
    saveLabel: subject ? 'Зберегти' : 'Додати предмет',
    save: (data) => request(subject ? `/subjects/${subject.id}` : '/subjects', {
      method: subject ? 'PATCH' : 'POST',
      data: subject ? { name: data.name.trim() } : { name: data.name.trim(), semester_id: semesterId },
    }),
    success: subject ? 'Предмет оновлено' : 'Предмет додано',
    remove: subject ? {
      label: 'Видалити предмет', title: 'Видалити предмет?',
      message: 'Усі оцінки з цього предмета буде видалено.',
      path: `/subjects/${subject.id}`, success: 'Предмет видалено',
    } : null,
  });
}

function editGrade(subject, grade) {
  const max = state.semester.grading_scale;
  const min = max === 100 ? 0 : 1;
  showEditor({
    title: grade ? 'Змінити оцінку' : 'Нова оцінка',
    fields: [{ name: 'value', label: subject.name, type: 'number', value: grade?.value, min, max, step: 1, inputmode: 'numeric' }],
    hint: `Допустима оцінка від ${min} до ${max}.`,
    saveLabel: grade ? 'Зберегти' : 'Додати оцінку',
    save: (data) => request(grade ? `/grades/${grade.id}` : '/grades', {
      method: grade ? 'PATCH' : 'POST',
      data: grade ? { value: Number(data.value) } : { value: Number(data.value), subject_id: subject.id },
    }),
    success: grade ? 'Оцінку оновлено' : 'Оцінку додано',
    invalid: `Введіть ціле число від ${min} до ${max}.`,
    remove: grade ? {
      label: 'Видалити оцінку', title: 'Видалити оцінку?',
      message: 'Середній бал оновиться після видалення.',
      path: `/grades/${grade.id}`, success: 'Оцінку видалено',
    } : null,
  });
}

function editGoal() {
  const semester = state.semester;
  if (!semester) return;
  const goal = state.progress?.target_average ?? null;
  const path = `/semesters/${semester.id}/scholarship-settings`;
  const min = semester.grading_scale === 100 ? 0.01 : 1;
  showEditor({
    title: goal === null ? 'Встановити ціль' : 'Змінити ціль',
    fields: [{ name: 'target_average', label: 'Цільовий середній бал', type: 'number', value: goal, min, max: semester.grading_scale, step: 0.01, inputmode: 'decimal' }],
    hint: 'Навчальна ціль. Умови призначення стипендії встановлює заклад освіти.',
    save: (data) => request(path, { method: 'PUT', data: { target_average: data.target_average } }),
    success: 'Ціль збережено',
    invalid: `Введіть значення від ${formatScore(min)} до ${formatScore(semester.grading_scale)} з точністю до двох знаків після коми.`,
    remove: goal !== null ? {
      label: 'Видалити ціль', title: 'Видалити ціль?',
      message: 'Прогноз і поступ знову з’являться після додавання нової цілі.',
      path, success: 'Ціль видалено',
    } : null,
  });
}

byId('editor-form').addEventListener('submit', async (event) => {
  event.preventDefault();
  const operation = editOperation;
  const data = Object.fromEntries(new FormData(event.currentTarget));
  setNotice(byId('editor-error'), '');
  setDialogBusy(editor, true);
  try {
    const result = await operation.save(data);
    await afterMutation(operation.success, operation.preferredSemester?.(result));
  } catch (error) {
    setNotice(byId('editor-error'), apiMessage(error, operation));
  } finally {
    setDialogBusy(editor, false);
  }
});

byId('confirm-form').addEventListener('submit', async (event) => {
  event.preventDefault();
  const operation = confirmationOperation;
  setNotice(byId('confirm-error'), '');
  setDialogBusy(confirmDialog, true);
  try {
    await request(operation.path, { method: 'DELETE' });
    if (operation.path === '/students/me') { clearToken(); window.location.replace('/login'); return; }
    await afterMutation(operation.success);
  } catch (error) {
    setNotice(byId('confirm-error'), apiMessage(error));
  } finally {
    setDialogBusy(confirmDialog, false);
  }
});

for (const dialog of [editor, confirmDialog]) {
  dialog.addEventListener('cancel', (event) => {
    if (dialog.hasAttribute('aria-busy')) event.preventDefault();
  });
}
for (const closer of document.querySelectorAll('[data-close-editor]')) {
  closer.addEventListener('click', () => editor.close());
}
byId('editor-delete').addEventListener('click', () => showConfirmation(editOperation.remove));
byId('confirm-cancel').addEventListener('click', () => confirmDialog.close());
byId('profile-button').addEventListener('click', editProfile);
byId('logout-button').addEventListener('click', () => { clearToken(); window.location.replace('/login'); });
byId('setup-action').addEventListener('click', () => state.student ? editSemester() : editProfile());
byId('new-term').addEventListener('click', () => editSemester());
byId('term-settings').addEventListener('click', () => editSemester(state.semester));
byId('term-select').addEventListener('change', (event) => reload(event.target.value));
byId('new-subject').addEventListener('click', () => editSubject());
byId('goal-button').addEventListener('click', editGoal);
byId('forecast-form').addEventListener('submit', calculateForecast);
byId('retry').addEventListener('click', () => reload());

function selectNavigation() {
  const target = window.location.hash || '#dashboard';
  for (const link of document.querySelectorAll('.nav-link')) {
    const active = link.hash === target;
    link.classList.toggle('is-current', active);
    if (active) link.setAttribute('aria-current', 'location');
    else link.removeAttribute('aria-current');
  }
}
window.addEventListener('hashchange', selectNavigation);
selectNavigation();
void reload();

