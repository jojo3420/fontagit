import { test, expect } from '@playwright/test';

const routes = [
  { path: '/', name: 'Home' },
  { path: '/fonts', name: 'Fonts List' },
  { path: '/fonts/pretendard', name: 'Pretendard Detail' },
  { path: '/fonts/sandoll-gothic-neo', name: 'Sandoll Gothic Neo Detail' },
  { path: '/trends', name: 'Trends' },
  { path: '/not-found', name: '404 Page' },
];

routes.forEach((route) => {
  test(`smoke: ${route.name} loads without console errors`, async ({
    page,
  }) => {
    const errors: string[] = [];

    page.on('console', (msg) => {
      if (msg.type() === 'error') {
        errors.push(`[${msg.type()}] ${msg.text()}`);
      }
    });

    await page.goto(route.path, { waitUntil: 'networkidle' });

    expect(errors).toEqual([]);
  });

  test(`smoke: ${route.name} captures screenshot (desktop/mobile)`, async ({
    page,
  }) => {
    await page.goto(route.path, { waitUntil: 'networkidle' });

    // Capture screenshot for desktop and mobile viewports
    await expect(page).toHaveScreenshot(`${route.name.replace(/\s+/g, '-').toLowerCase()}-screenshot.png`, {
      maxDiffPixels: 100,
    });
  });
});

test('preview input updates specimen live', async ({ page }) => {
  await page.goto('/fonts/pretendard/', { waitUntil: 'networkidle' });
  await page.getByLabel('미리보기 입력').fill('가나다 테스트');
  await expect(page.getByText('가나다 테스트').first()).toBeVisible();
});
