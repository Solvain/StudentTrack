import { request, setToken, ApiError } from './api.mjs';

for (const id of ['login-form', 'register-form']) {
  const form = document.getElementById(id);
  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    const data = Object.fromEntries(new FormData(form));
    const errorBox = document.getElementById('auth-error');
    const button = form.querySelector('button');
    errorBox.textContent = '';
    button.disabled = true;
    try {
      if (id === 'register-form') await request('/auth/register', { method: 'POST', data });
      const result = await request('/auth/login', {
        method: 'POST', data: { username: data.username, password: data.password },
      });
      setToken(result.access_token);
      window.location.replace('/');
    } catch (error) {
      errorBox.textContent = error instanceof ApiError && error.status === 401
        ? 'Неправильний логін або пароль.'
        : error instanceof ApiError && error.status === 409
          ? 'Цей логін уже зайнятий.'
          : 'Перевірте дані або спробуйте пізніше.';
    } finally { button.disabled = false; }
  });
}
