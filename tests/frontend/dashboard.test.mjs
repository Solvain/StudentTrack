import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { test } from 'node:test';

import { ApiError, formatScore, request } from '../../app/static/api.mjs';

test('the dashboard exposes its three sections, forms and bundled assets', async () => {
  const html = await readFile(new URL('../../app/static/index.html', import.meta.url), 'utf8');

  for (const id of ['dashboard', 'subjects', 'forecast', 'forecast-form', 'editor', 'confirm-dialog']) {
    assert.match(html, new RegExp(`id="${id}"`));
  }
  assert.match(html, /<html lang="uk">/);
  assert.match(html, /href="\/static\/styles\.css"/);
  assert.match(html, /src="\/static\/app\.mjs"/);
});

test('the zero allowed by the 100-point scale is different from a missing score', () => {
  assert.equal(formatScore(0), '0,00');
  assert.equal(formatScore('4.50'), '4,50');
  assert.equal(formatScore(null), '—');
});

test('requests use JSON and a successful delete has no body', async () => {
  const fetcher = async (path, init) => {
    assert.equal(path, '/api/grades/3');
    assert.equal(init.method, 'PATCH');
    assert.equal(init.headers['Content-Type'], 'application/json');
    assert.deepEqual(JSON.parse(init.body), { value: 0 });
    return new Response(null, { status: 204 });
  };

  assert.equal(await request('/grades/3', { method: 'PATCH', data: { value: 0 }, fetcher }), null);
});

test('API errors preserve status and detail and only a requested 404 returns null', async () => {
  const fetcher = async () => Response.json({ detail: 'not found' }, { status: 404 });

  assert.equal(await request('/students/me', { missing: true, fetcher }), null);
  await assert.rejects(request('/students/me', { fetcher }), (error) => {
    assert.ok(error instanceof ApiError);
    assert.equal(error.status, 404);
    assert.equal(error.detail, 'not found');
    return true;
  });
});

test('login and registration forms default to POST', async () => {
  const html = await readFile(new URL('../../app/static/login.html', import.meta.url), 'utf8');
  for (const id of ['login-form', 'register-form']) {
    assert.match(html, new RegExp(`<form id="${id}" method="post">`));
  }
});
