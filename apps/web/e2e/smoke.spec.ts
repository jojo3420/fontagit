import { test, expect } from '@playwright/test';

const routes = [
  { path: '/', name: 'Home' },
  { path: '/fonts', name: 'Fonts List' },
  { path: '/fonts/pretendard', name: 'Pretendard Detail' },
  { path: '/fonts/sandoll-gothic-neo', name: 'Sandoll Gothic Neo Detail' },
  { path: '/trends', name: 'Trends' },
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

test('smoke: 404 Page renders branded content', async ({ page }) => {
  await page.goto('/not-found', { waitUntil: 'networkidle' });

  // Assert branded 404 copy is visible
  await expect(page.getByText(/아지트 입구로 모실게요/)).toBeVisible();

  // Assert home button exists
  await expect(page.getByRole('link', { name: '홈으로 돌아가기' })).toBeVisible();
});

test('smoke: 404 Page captures screenshot (desktop/mobile)', async ({ page }) => {
  await page.goto('/not-found', { waitUntil: 'networkidle' });

  // Capture screenshot for desktop and mobile viewports
  await expect(page).toHaveScreenshot('404-page-screenshot.png', {
    maxDiffPixels: 100,
  });
});

test('preview input updates specimen live', async ({ page }) => {
  await page.goto('/fonts/pretendard/', { waitUntil: 'networkidle' });
  await page.getByLabel('미리보기 입력').fill('가나다 테스트');
  await expect(page.getByText('가나다 테스트').first()).toBeVisible();
});
