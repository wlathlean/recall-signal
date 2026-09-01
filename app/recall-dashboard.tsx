'use client';

import { useEffect, useMemo, useState } from 'react';

type Product = { name: string; codes?: string; recallNumber?: string };
type RecallRecord = {
  id: string; section: 'food' | 'pet_food' | 'products'; category: string; title: string;
  brand: string; description: string; reason: string; action: string; date: string; status: string;
  classification: string; severity: number; states: string[]; distribution: string; retailers: string[];
  allergens: string[]; codes: string; source: string; sourceUrl: string; products?: Product[];
};
type Source = { name: string; ok: boolean; records: number; url: string; note?: string };
type Trend = { month: string; food: number; pet_food: number; products: number };
type TrackerData = { generatedAt: string; detailWindowDays: number; sources: Source[]; records: RecallRecord[]; trends: Trend[] };
type Vehicle = { year: string; make: string; model: string };
type VehicleRecall = {
  Manufacturer: string; NHTSACampaignNumber: string; ReportReceivedDate: string; Component: string;
  Summary: string; Consequence: string; Remedy: string; parkIt?: boolean; parkOutSide?: boolean;
};
type Settings = { retailers: string[]; brands: string; upcs: string; categories: string[]; vehicles: Vehicle[] };

const DATA_URL = process.env.NEXT_PUBLIC_RECALL_DATA_URL || '/data/tracker.json';
const retailerOptions = ['Amazon', 'Costco', 'Walmart', 'Target', 'H-E-B', 'Kroger', 'QFC', 'Fred Meyer', 'Safeway', 'Albertsons', 'WinCo', "Trader Joe's"];
const categoryOptions = ['Baby & child', 'Medicines & medical devices', 'Appliances & electronics', 'Furniture & home', 'Sports & outdoors', 'Tools & power equipment', 'Cosmetics & personal care', 'Pet products', 'Other consumer products'];
const defaultSettings: Settings = { retailers: retailerOptions, brands: '', upcs: '', categories: categoryOptions, vehicles: [] };
const tabs = [
  { key: 'food', label: 'Human food' }, { key: 'pet_food', label: 'Pet food' },
  { key: 'products', label: 'Products' }, { key: 'vehicles', label: 'Vehicles' }, { key: 'context', label: 'Context' },
] as const;

function formatDate(value: string, withTime = false) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat('en-US', withTime ? { dateStyle: 'medium', timeStyle: 'short', timeZone: 'America/Los_Angeles' } : { dateStyle: 'medium', timeZone: 'UTC' }).format(date);
}

function matchLevel(record: RecallRecord, settings: Settings) {
  const text = `${record.title} ${record.brand} ${record.description} ${record.codes}`.toLowerCase();
  const brandTerms = settings.brands.split(',').map((item) => item.trim().toLowerCase()).filter(Boolean);
  const upcs = settings.upcs.split(',').map((item) => item.replace(/\D/g, '')).filter(Boolean);
  const exact = upcs.some((upc) => upc.length >= 6 && text.replace(/\D/g, '').includes(upc)) || brandTerms.some((brand) => text.includes(brand));
  const retailer = record.retailers.some((item) => settings.retailers.some((saved) => item.toLowerCase().includes(saved.toLowerCase()) || saved.toLowerCase().includes(item.toLowerCase())));
  const region = record.states.includes('US') || record.states.some((state) => ['WA', 'TX', 'UT', 'CA'].includes(state));
  const priorityAllergen = record.allergens.includes('tree nuts') || record.allergens.includes('sesame');
  if (exact) return { score: 4, label: 'Exact watchlist match' };
  if (retailer && region) return { score: 3, label: 'Likely household match' };
  if (priorityAllergen && region) return { score: 3, label: 'Priority allergen' };
  if (region) return { score: 2, label: 'Possible regional match' };
  return { score: 1, label: 'General notice' };
}

function RecallCard({ record, settings }: { record: RecallRecord; settings: Settings }) {
  const match = matchLevel(record, settings);
  const locations = record.states.includes('US') ? 'Nationwide' : record.states.length ? record.states.join(', ') : 'Distribution not clearly specified';
  return (
    <article className={`recall-card severity-${record.severity}`}>
      <div className="recall-card-top">
        <span className={`match-badge match-${match.score}`}>{match.label}</span>
        <time dateTime={record.date}>{formatDate(record.date)}</time>
      </div>
      <p className="category">{record.category} · {record.classification}</p>
      <h3>{record.title}</h3>
      <p className="reason">{record.reason || record.description}</p>
      <div className="fact-row">
        <span><b>Where:</b> {locations}</span>
        {record.retailers.length > 0 && <span><b>Retailers:</b> {record.retailers.join(', ')}</span>}
        {record.allergens.length > 0 && <span><b>Allergens:</b> {record.allergens.join(', ')}</span>}
      </div>
      <div className="action-box"><span>What to do</span><p>{record.action}</p></div>
      <details>
        <summary>Product codes and source details</summary>
        {record.products && record.products.length > 0 && (
          <ul className="product-list">
            {record.products.slice(0, 30).map((product, index) => <li key={`${product.recallNumber}-${index}`}><b>{product.name}</b>{product.codes && <small>{product.codes}</small>}</li>)}
            {record.products.length > 30 && <li>Plus {record.products.length - 30} additional product entries—see the official source.</li>}
          </ul>
        )}
        {record.distribution && <p><b>Official distribution text:</b> {record.distribution}</p>}
        <a href={record.sourceUrl} target="_blank" rel="noreferrer">Open {record.source}</a>
      </details>
    </article>
  );
}

export default function RecallDashboard({ initialData }: { initialData: TrackerData }) {
  const [data, setData] = useState(initialData);
  const [active, setActive] = useState<(typeof tabs)[number]['key']>('food');
  const [search, setSearch] = useState('');
  const [filter, setFilter] = useState('all');
  const [limit, setLimit] = useState(36);
  const [settings, setSettings] = useState<Settings>(defaultSettings);
  const [watchOpen, setWatchOpen] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [vehicleDraft, setVehicleDraft] = useState<Vehicle>({ year: '', make: '', model: '' });
  const [vehicleResults, setVehicleResults] = useState<Record<string, VehicleRecall[]>>({});
  const [vehicleLoading, setVehicleLoading] = useState('');

  useEffect(() => {
    const saved = localStorage.getItem('recall-signal-settings');
    if (saved) {
      try { setSettings({ ...defaultSettings, ...JSON.parse(saved) }); } catch { /* keep safe defaults */ }
    }
  }, []);

  function saveSettings(next: Settings) {
    setSettings(next);
    localStorage.setItem('recall-signal-settings', JSON.stringify(next));
  }

  async function refreshData() {
    setRefreshing(true);
    try {
      const response = await fetch(`${DATA_URL}${DATA_URL.includes('?') ? '&' : '?'}v=${Date.now()}`, { cache: 'no-store' });
      if (!response.ok) throw new Error('Update unavailable');
      setData(await response.json());
    } finally { setRefreshing(false); }
  }

  const staleHours = (Date.now() - new Date(data.generatedAt).getTime()) / 36e5;
  const counts = useMemo(() => ({
    food: data.records.filter((item) => item.section === 'food').length,
    pet_food: data.records.filter((item) => item.section === 'pet_food').length,
    products: data.records.filter((item) => item.section === 'products').length,
    vehicles: settings.vehicles.length,
    context: data.trends.length,
  }), [data, settings.vehicles.length]);

  const visible = useMemo(() => {
    if (!['food', 'pet_food', 'products'].includes(active)) return [];
    const query = search.trim().toLowerCase();
    return data.records
      .filter((item) => item.section === active)
      .filter((item) => filter === 'all' || (filter === 'investigation' ? item.category === 'Investigation' : item.allergens.includes(filter)))
      .filter((item) => !query || `${item.title} ${item.brand} ${item.reason} ${item.distribution} ${item.retailers.join(' ')}`.toLowerCase().includes(query))
      .filter((item) => active !== 'products' || settings.categories.includes(item.category))
      .sort((a, b) => matchLevel(b, settings).score - matchLevel(a, settings).score || b.severity - a.severity || b.date.localeCompare(a.date));
  }, [active, data.records, filter, search, settings]);

  const hero = useMemo(() => visible.find((item) => matchLevel(item, settings).score >= 3) || visible[0], [visible, settings]);
  const sourceFailures = data.sources.filter((source) => !source.ok);

  async function checkVehicle(vehicle: Vehicle) {
    const key = `${vehicle.year} ${vehicle.make} ${vehicle.model}`;
    setVehicleLoading(key);
    try {
      const params = new URLSearchParams({ modelYear: vehicle.year, make: vehicle.make, model: vehicle.model });
      const response = await fetch(`https://api.nhtsa.gov/recalls/recallsByVehicle?${params}`);
      const payload = await response.json();
      setVehicleResults((current) => ({ ...current, [key]: payload.results || [] }));
    } finally { setVehicleLoading(''); }
  }

  function addVehicle() {
    if (!vehicleDraft.year || !vehicleDraft.make || !vehicleDraft.model) return;
    saveSettings({ ...settings, vehicles: [...settings.vehicles, vehicleDraft] });
    setVehicleDraft({ year: '', make: '', model: '' });
  }

  const maxTrend = Math.max(1, ...data.trends.map((item) => item.food + item.pet_food + item.products));

  return (
    <main>
      <header className="site-header">
        <div><p className="eyebrow">Family recall watch</p><h1>Recall Signal</h1></div>
        <button className="watch-button" type="button" onClick={() => setWatchOpen(true)}>Your watchlist</button>
      </header>

      <section className={`status-strip ${staleHours > 36 ? 'stale' : ''}`} aria-label="Tracker status">
        <div><span className="status-dot" /><strong>{staleHours > 36 ? 'Data may be stale' : `Updated ${formatDate(data.generatedAt, true)} PT`}</strong><span>Scheduled 6:00 AM + 3:00 PM Pacific</span></div>
        <button type="button" onClick={refreshData} disabled={refreshing}>{refreshing ? 'Checking…' : 'Check for updates'}</button>
      </section>

      {sourceFailures.length > 0 && <div className="coverage-warning"><b>Coverage notice:</b> {sourceFailures.map((source) => source.name).join(' and ')} could not be refreshed. <button onClick={() => setActive('context')}>See source status</button></div>}

      <nav className="section-tabs" aria-label="Recall sections">
        {tabs.map((tab) => <button className={active === tab.key ? 'active' : ''} key={tab.key} type="button" onClick={() => { setActive(tab.key); setLimit(36); }}><span>{tab.label}</span><b>{counts[tab.key]}</b></button>)}
      </nav>

      {['food', 'pet_food', 'products'].includes(active) && (
        <>
          {hero && <section className="hero-grid"><RecallCard record={hero} settings={settings} /><aside className="local-card"><p className="eyebrow">Your areas</p><h2>Household relevance</h2><div className="place-row"><span>98074 + 25 miles</span><b>WA</b></div><div className="place-row"><span>75033 + 25 miles</span><b>TX</b></div><div className="place-row quiet"><span>UT + CA statewide</span><b>2</b></div><p className="privacy-note">Preferences remain in this browser. “Possible match” means you still need to compare the product, codes, and official distribution details.</p></aside></section>}
          <section className="recall-browser">
            <div className="browser-heading"><div><p className="eyebrow">Current notices</p><h2>{visible.length} matching {active === 'food' ? 'human-food' : active === 'pet_food' ? 'pet-food' : 'product'} events</h2></div><input aria-label="Search recalls" value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search brand, product, retailer…" /></div>
            {active === 'food' && <div className="filter-row"><button className={filter === 'all' ? 'active-filter' : ''} onClick={() => setFilter('all')}>All food</button><button className={filter === 'tree nuts' ? 'active-filter' : ''} onClick={() => setFilter('tree nuts')}>Tree nuts</button><button className={filter === 'sesame' ? 'active-filter' : ''} onClick={() => setFilter('sesame')}>Sesame</button><button className={filter === 'investigation' ? 'active-filter' : ''} onClick={() => setFilter('investigation')}>Investigations</button></div>}
            <div className="recall-list">{visible.slice(0, limit).map((record) => <RecallCard key={record.id} record={record} settings={settings} />)}</div>
            {limit < visible.length && <button className="load-more" onClick={() => setLimit((current) => current + 36)}>Load more notices</button>}
          </section>
        </>
      )}

      {active === 'vehicles' && <section className="panel-page"><div className="browser-heading"><div><p className="eyebrow">NHTSA vehicle recall check</p><h2>Saved vehicles</h2></div><button className="primary-button" onClick={() => setWatchOpen(true)}>Add vehicle</button></div><p className="section-note">Year/make/model results are general. NHTSA says a VIN search is required to identify unrepaired recalls on a specific vehicle.</p>{settings.vehicles.length === 0 && <div className="empty-state">Add a vehicle to your device-local watchlist to check general NHTSA recalls.</div>}{settings.vehicles.map((vehicle, index) => { const key = `${vehicle.year} ${vehicle.make} ${vehicle.model}`; const results = vehicleResults[key]; return <article className="vehicle-card" key={`${key}-${index}`}><div><p className="category">Saved on this device</p><h3>{key}</h3></div><button onClick={() => checkVehicle(vehicle)} disabled={vehicleLoading === key}>{vehicleLoading === key ? 'Checking…' : 'Check NHTSA'}</button>{results && <div className="vehicle-results"><b>{results.length} general recall result{results.length === 1 ? '' : 's'}</b>{results.map((item) => <details key={item.NHTSACampaignNumber}><summary>{item.Component} · {item.NHTSACampaignNumber}</summary><p>{item.Summary}</p><p><b>Risk:</b> {item.Consequence}</p><p><b>Remedy:</b> {item.Remedy}</p><a href={`https://www.nhtsa.gov/recalls?nhtsaId=${item.NHTSACampaignNumber}`} target="_blank" rel="noreferrer">Open NHTSA recall</a></details>)}</div>}</article>; })}<a className="nhtsa-link" href="https://www.nhtsa.gov/recalls" target="_blank" rel="noreferrer">Run an exact VIN check at NHTSA</a></section>}

      {active === 'context' && <section className="panel-page"><p className="eyebrow">Two-year context</p><h2>Recall events by reporting month</h2><p className="section-note">Counts represent grouped recall events where possible—not every individual UPC or SKU. Changes can reflect agency reporting practices as well as actual safety activity.</p><div className="trend-chart" aria-label="Monthly recall-event chart">{data.trends.map((item) => { const total = item.food + item.pet_food + item.products; return <div className="trend-column" key={item.month} title={`${item.month}: ${total} events`}><span style={{ height: `${Math.max(2, (total / maxTrend) * 100)}%` }} /><small>{item.month.endsWith('-01') ? item.month.slice(0, 4) : ''}</small></div>; })}</div><h2 className="source-title">Source health</h2><div className="source-grid">{data.sources.map((source) => <a href={source.url} target="_blank" rel="noreferrer" className={source.ok ? 'source-ok' : 'source-fail'} key={source.name}><span>{source.ok ? 'Available' : 'Needs attention'}</span><b>{source.name}</b><small>{source.ok ? `${source.records.toLocaleString()} historical records processed` : source.note}</small></a>)}</div></section>}

      {watchOpen && <div className="modal-backdrop" role="presentation" onMouseDown={() => setWatchOpen(false)}><section className="watch-modal" role="dialog" aria-modal="true" aria-labelledby="watch-title" onMouseDown={(event) => event.stopPropagation()}><div className="modal-heading"><div><p className="eyebrow">Private on-device settings</p><h2 id="watch-title">Your watchlist</h2></div><button aria-label="Close watchlist" onClick={() => setWatchOpen(false)}>×</button></div><label>Brands or product names <small>Separate entries with commas</small><input value={settings.brands} onChange={(event) => saveSettings({ ...settings, brands: event.target.value })} placeholder="Example: Gerber, Graco" /></label><label>UPCs <small>Separate entries with commas</small><input value={settings.upcs} onChange={(event) => saveSettings({ ...settings, upcs: event.target.value })} inputMode="numeric" /></label><fieldset><legend>Retailers</legend><div className="check-grid">{retailerOptions.map((retailer) => <label key={retailer}><input type="checkbox" checked={settings.retailers.includes(retailer)} onChange={(event) => saveSettings({ ...settings, retailers: event.target.checked ? [...settings.retailers, retailer] : settings.retailers.filter((item) => item !== retailer) })} />{retailer}</label>)}</div></fieldset><fieldset><legend>Non-food categories</legend><div className="check-grid">{categoryOptions.map((category) => <label key={category}><input type="checkbox" checked={settings.categories.includes(category)} onChange={(event) => saveSettings({ ...settings, categories: event.target.checked ? [...settings.categories, category] : settings.categories.filter((item) => item !== category) })} />{category}</label>)}</div></fieldset><fieldset><legend>Add vehicle</legend><div className="vehicle-form"><input aria-label="Vehicle year" placeholder="Year" value={vehicleDraft.year} onChange={(event) => setVehicleDraft({ ...vehicleDraft, year: event.target.value })} /><input aria-label="Vehicle make" placeholder="Make" value={vehicleDraft.make} onChange={(event) => setVehicleDraft({ ...vehicleDraft, make: event.target.value })} /><input aria-label="Vehicle model" placeholder="Model" value={vehicleDraft.model} onChange={(event) => setVehicleDraft({ ...vehicleDraft, model: event.target.value })} /><button onClick={addVehicle}>Add</button></div>{settings.vehicles.map((vehicle, index) => <div className="saved-vehicle" key={`${vehicle.year}-${vehicle.make}-${vehicle.model}-${index}`}><span>{vehicle.year} {vehicle.make} {vehicle.model}</span><button onClick={() => saveSettings({ ...settings, vehicles: settings.vehicles.filter((_, itemIndex) => itemIndex !== index) })}>Remove</button></div>)}</fieldset><p className="privacy-note">This proof of concept stores these settings only in this browser. Clearing browser data removes them.</p><button className="save-button" onClick={() => setWatchOpen(false)}>Done</button></section></div>}
    </main>
  );
}
