import { expect, test } from '@playwright/test';
import type { GraphResponse } from '../src/api/types';

const service = { id: 'svc-1', name: 'Demo SQL', fullyQualifiedName: 'Demo SQL' };
const database = { id: 'db-1', name: 'Commerce', fullyQualifiedName: 'Demo SQL.Commerce' };
const schema = { id: 'schema-1', name: 'Sales', fullyQualifiedName: 'Demo SQL.Commerce.Sales' };
const graph: GraphResponse = {
  source: 'live', schema, warnings: [],
  tables: [
    {
      id: 'customer', name: 'Customer', fullyQualifiedName: `${schema.fullyQualifiedName}.Customer`, entityType: 'table',
      description: 'Customers who place orders.', owner: 'Data Architecture', tags: ['PII.Sensitive'], tier: 'Tier1',
      columns: [{ name: 'id', dataType: 'INT', nullable: false, primaryKey: true, foreignKey: false, description: 'Customer identifier.' }],
    },
    {
      id: 'orders', name: 'Orders', fullyQualifiedName: `${schema.fullyQualifiedName}.Orders`, entityType: 'table',
      description: null, owner: null, tags: [], tier: null,
      columns: [{ name: 'customer_id', dataType: 'INT', nullable: false, primaryKey: false, foreignKey: true, description: null }],
    },
    {
      id: 'order-summary', name: 'Order Summary', fullyQualifiedName: `${schema.fullyQualifiedName}.Order Summary`, entityType: 'view',
      description: 'Order reporting view.', owner: 'Data Architecture', tags: [], tier: 'Tier1',
      columns: [{ name: 'order_id', dataType: 'INT', nullable: false, primaryKey: false, foreignKey: true, description: null }],
    },
  ],
  relationships: [
    { id: 'fk-orders-customer', sourceTableId: 'orders', sourceColumn: 'customer_id', targetTableId: 'customer', targetColumn: 'id' },
    { id: 'fk-summary-orders', sourceTableId: 'order-summary', sourceColumn: 'order_id', targetTableId: 'orders', targetColumn: 'customer_id' },
  ],
};

test('explores the catalog, manipulates the diagram, inspects metadata, and labels fallback', async ({ page }) => {
  const errors: string[] = [];
  page.on('pageerror', (error) => errors.push(error.message));
  let sample = false;
  const requests: string[] = [];
  await page.route(/\/api\/[^/]/, async (route) => {
    const url = new URL(route.request().url());
    if (!url.pathname.startsWith('/api/')) return route.continue();
    requests.push(`${route.request().method()} ${url.pathname}${url.search}`);
    let body: unknown;
    if (url.pathname === '/api/services') body = [service];
    else if (url.pathname === '/api/databases' && url.searchParams.get('serviceId') === service.id) body = [database];
    else if (url.pathname === '/api/schemas' && url.searchParams.get('databaseId') === database.id) body = [schema];
    else if (url.pathname === `/api/schemas/${schema.id}/graph`) body = { ...graph, source: sample ? 'sample' : 'live', warnings: sample ? ['OpenMetadata is unavailable; displaying the bundled sample.'] : [] };
    else throw new Error(`Unexpected backend route: ${url.pathname}${url.search}`);
    await route.fulfill({ json: body });
  });

  async function selectSchema() {
    await page.getByRole('combobox', { name: 'Database service', exact: true }).selectOption(service.id);
    await page.getByRole('combobox', { name: 'Database', exact: true }).selectOption(database.id);
    await page.getByRole('combobox', { name: 'Schema', exact: true }).selectOption(schema.id);
  }

  await page.goto('/');
  await selectSchema();
  const customer = page.getByRole('group', { name: 'Customer table', exact: true });
  const summary = page.getByRole('group', { name: 'Order Summary view', exact: true });
  const relationship = page.getByRole('group', { name: 'Orders.customer_id references Customer.id', exact: true });
  await expect(page.getByRole('radio', { name: 'Tables', exact: true })).toBeChecked();
  await expect(summary).toHaveCount(0);
  await page.getByText('Views', { exact: true }).click();
  await expect(customer).toHaveCount(0);
  await expect(summary).toBeVisible();
  await page.getByText('Both', { exact: true }).click();
  await expect(customer).toBeVisible();
  await expect(summary).toBeVisible();
  await page.getByText('Tables', { exact: true }).click();
  await expect(customer).toBeVisible();
  // Horizontal SVG paths have a zero-height bounding box, so assert that the
  // accessible rendered edge exists rather than relying on HTML visibility.
  await expect(relationship).toHaveCount(1);
  await expect(relationship.getByText('customer_id → id', { exact: true })).toBeVisible();
  await expect(customer.getByRole('list', { name: 'Customer columns', exact: true })).toContainText('INT');
  await expect(customer.getByRole('img', { name: 'Primary key', exact: true })).toBeVisible();
  await expect(page.getByText('Sample data — OpenMetadata unavailable')).toBeHidden();
  await expect(page.getByText('Laying out diagram…')).toBeHidden();

  // A real pointer gesture exercises React Flow's table drag handle.
  const before = await customer.boundingBox();
  if (!before) throw new Error('Customer table has no visible drag handle');
  const handle = { x: before.x + before.width / 2, y: before.y + 3 };
  await page.mouse.move(handle.x, handle.y);
  await page.mouse.down();
  await page.mouse.move(handle.x + 80, handle.y + 60, { steps: 8 });
  await page.mouse.up();
  await expect.poll(async () => (await customer.boundingBox())?.x).not.toBe(before.x);

  await page.getByRole('button', { name: 'Collapse Customer', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Expand Customer', exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Hide Customer', exact: true }).click();
  await expect(customer).toBeHidden();
  await expect(relationship).toBeHidden();
  await page.getByRole('button', { name: 'Restore Customer', exact: true }).click();
  await expect(customer).toBeVisible();
  await expect(relationship).toHaveCount(1);
  await page.getByRole('button', { name: 'Expand Customer', exact: true }).click();
  await page.getByRole('button', { name: 'Zoom In', exact: true }).click();
  await page.getByRole('button', { name: 'Zoom Out', exact: true }).click();
  await page.getByRole('button', { name: 'Fit View', exact: true }).click();
  await page.getByRole('toolbar', { name: 'Diagram controls' }).getByRole('button', { name: 'Relayout diagram', exact: true }).click();
  await expect(page.getByText('Laying out diagram…')).toBeHidden();

  await customer.click();
  const inspector = page.getByRole('complementary');
  await expect(inspector).toContainText('Data Architecture');
  await expect(inspector).toContainText('Customers who place orders.');
  await expect(inspector).toContainText('PII.Sensitive');
  await expect(inspector).toContainText('Tier1');
  await expect(inspector.getByRole('region', { name: 'Columns', exact: true })).toContainText('Customer identifier.');
  await expect(inspector.getByRole('region', { name: 'Incoming references', exact: true })).toContainText('Orders.customer_id → Customer.id');

  await page.getByRole('button', { name: 'Hide Customer', exact: true }).click();
  await page.reload();
  await selectSchema();
  await expect(customer).toBeVisible();
  await expect(page.getByRole('button', { name: 'Collapse Customer', exact: true })).toBeVisible();
  await expect(page.getByRole('complementary')).toContainText('Diagram overview');

  sample = true;
  await page.getByRole('combobox', { name: 'Schema', exact: true }).selectOption('');
  await page.getByRole('combobox', { name: 'Schema', exact: true }).selectOption(schema.id);
  await expect(page.getByRole('status', { name: 'Data source' })).toHaveText('Sample data — OpenMetadata unavailable');
  expect(requests).toContain('GET /api/services');
  expect(requests).toContain('GET /api/databases?serviceId=svc-1');
  expect(requests).toContain('GET /api/schemas?databaseId=db-1');
  expect(requests).toContain('GET /api/schemas/schema-1/graph');
  expect(requests.every((request) => request.startsWith('GET '))).toBe(true);
  expect(errors).toEqual([]);
});
