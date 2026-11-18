import React, { useEffect, useState } from 'react';
import { api } from './api';
import { BidCreatePayload, RfqDetail, RfqSummary, TriggerType } from './types';

function toLocalDatetimeInputValue(date: Date): string {
  const pad = (n: number) => String(n).padStart(2, '0');
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

function formatDateTime(iso: string | null): string {
  if (!iso) return '—';
  const d = new Date(iso);
  return d.toLocaleString(undefined, {
    year: 'numeric',
    month: 'short',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  });
}

function formatCountdown(targetIso: string, nowMs: number): string {
  const diffSec = Math.floor((new Date(targetIso).getTime() - nowMs) / 1000);
  if (diffSec <= 0) return '00m 00s';
  const hrs = Math.floor(diffSec / 3600);
  const mins = Math.floor((diffSec % 3600) / 60);
  const secs = diffSec % 60;
  if (hrs > 0) {
    return `${hrs}h ${String(mins).padStart(2, '0')}m ${String(secs).padStart(2, '0')}s`;
  }
  return `${String(mins).padStart(2, '0')}m ${String(secs).padStart(2, '0')}s`;
}

function triggerLabel(t: TriggerType): string {
  if (t === 'BID_RECEIVED') return 'Bid Received in Last X Min';
  if (t === 'ANY_RANK_CHANGE') return 'Any Supplier Rank Change in Last X Min';
  return 'Lowest Bidder (L1) Rank Change in Last X Min';
}

function statusBadgeClass(status: string): string {
  if (status === 'ACTIVE') return 'badge badge-active';
  if (status === 'SCHEDULED') return 'badge badge-scheduled';
  if (status === 'FORCE_CLOSED') return 'badge badge-force-closed';
  return 'badge badge-closed';
}

export function App() {
  const [view, setView] = useState<'LIST' | 'CREATE' | 'DETAIL'>('LIST');
  const [selectedRfqId, setSelectedRfqId] = useState<string | null>(null);
  const [rfqs, setRfqs] = useState<RfqSummary[]>([]);
  const [detail, setDetail] = useState<RfqDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [nowMs, setNowMs] = useState<number>(Date.now());

  // Create RFQ form state
  const [refId, setRefId] = useState('');
  const [name, setName] = useState('');
  const [bidStart, setBidStart] = useState('');
  const [bidClose, setBidClose] = useState('');
  const [forcedClose, setForcedClose] = useState('');
  const [pickupDate, setPickupDate] = useState('');
  const [windowMin, setWindowMin] = useState(10);
  const [extMin, setExtMin] = useState(5);
  const [triggerType, setTriggerType] = useState<TriggerType>('L1_CHANGE');

  // Quote submission form state
  const [supplierId, setSupplierId] = useState('SUP-001');
  const [supplierName, setSupplierName] = useState('Maersk Global Logistics');
  const [carrierName, setCarrierName] = useState('Maersk Line');
  const [freightCharges, setFreightCharges] = useState('1050');
  const [originCharges, setOriginCharges] = useState('120');
  const [destinationCharges, setDestinationCharges] = useState('90');
  const [transitDays, setTransitDays] = useState('18');
  const [quoteValidity, setQuoteValidity] = useState('2026-12-15');

  // 1-second ticker for live countdowns
  useEffect(() => {
    const t = setInterval(() => setNowMs(Date.now()), 1000);
    return () => clearInterval(t);
  }, []);

  // Poll listing or detail every 3 seconds
  useEffect(() => {
    if (view === 'LIST') {
      loadList();
      const interval = setInterval(loadList, 3000);
      return () => clearInterval(interval);
    }
    if (view === 'DETAIL' && selectedRfqId) {
      loadDetail(selectedRfqId);
      const interval = setInterval(() => loadDetail(selectedRfqId), 3000);
      return () => clearInterval(interval);
    }
  }, [view, selectedRfqId]);

  async function loadList() {
    try {
      const data = await api.listRfqs();
      setRfqs(data);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Failed to load RFQs');
    }
  }

  async function loadDetail(id: string) {
    try {
      const data = await api.getRfq(id);
      setDetail(data);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Failed to load RFQ details');
    }
  }

  function initCreateFormDefaults() {
    const now = new Date();
    const suffix = String(now.getHours()).padStart(2, '0') + String(now.getMinutes()).padStart(2, '0');
    setRefId(`RFQ-2026-${suffix}`);
    setName('Mumbai (INNSA) to Rotterdam (NLRTM) - 40ft FCL');
    setBidStart(toLocalDatetimeInputValue(new Date(now.getTime() - 5 * 60000)));
    setBidClose(toLocalDatetimeInputValue(new Date(now.getTime() + 8 * 60000)));
    setForcedClose(toLocalDatetimeInputValue(new Date(now.getTime() + 25 * 60000)));
    setPickupDate(toLocalDatetimeInputValue(new Date(now.getTime() + 7 * 86400000)));
    setWindowMin(10);
    setExtMin(5);
    setTriggerType('L1_CHANGE');
  }

  function openCreateView() {
    setError(null);
    setNotice(null);
    initCreateFormDefaults();
    setView('CREATE');
  }

  function openDetailView(id: string) {
    setError(null);
    setNotice(null);
    setSelectedRfqId(id);
    setDetail(null);
    setView('DETAIL');
  }

  async function handleSeedDemo() {
    setError(null);
    setNotice(null);
    setLoading(true);
    try {
      await api.seedDemo();
      await loadList();
      setNotice('Seeded 3 active sample British Auctions inside their trigger windows.');
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Failed to seed demo auctions');
    } finally {
      setLoading(false);
    }
  }

  async function handleDeleteRfq(id: string, ref: string) {
    setError(null);
    setNotice(null);
    try {
      await api.deleteRfq(id);
      setNotice(`Deleted RFQ ${ref}.`);
      if (view === 'DETAIL') {
        setView('LIST');
      } else {
        await loadList();
      }
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Failed to delete RFQ');
    }
  }

  async function handleCreateRfq(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setNotice(null);

    const startDt = new Date(bidStart);
    const closeDt = new Date(bidClose);
    const forcedDt = new Date(forcedClose);
    const pickupDt = new Date(pickupDate);

    if (closeDt <= startDt) {
      setError('Validation Rule: Bid Close Time must be greater than Bid Start Time.');
      return;
    }
    if (forcedDt <= closeDt) {
      setError('Validation Rule: Forced Bid Close Time must always be greater than Bid Close Time.');
      return;
    }

    setLoading(true);
    try {
      const created = await api.createRfq({
        reference_id: refId.trim(),
        name: name.trim(),
        bid_start_at: startDt.toISOString(),
        bid_close_at: closeDt.toISOString(),
        forced_close_at: forcedDt.toISOString(),
        pickup_date: pickupDt.toISOString(),
        config: {
          trigger_window_minutes: Number(windowMin),
          extension_minutes: Number(extMin),
          trigger_type: triggerType,
        },
      });
      setNotice(`Created British Auction ${created.reference_id}.`);
      openDetailView(created.id);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to create RFQ');
    } finally {
      setLoading(false);
    }
  }

  async function handleSubmitBid(e: React.FormEvent) {
    e.preventDefault();
    if (!selectedRfqId || !detail) return;
    setError(null);
    setNotice(null);

    const payload: BidCreatePayload = {
      supplier_id: supplierId.trim(),
      supplier_name: supplierName.trim(),
      carrier_name: carrierName.trim(),
      freight_charges: Number(freightCharges),
      origin_charges: Number(originCharges),
      destination_charges: Number(destinationCharges),
      transit_time_days: Number(transitDays),
      quote_validity: quoteValidity.trim(),
    };

    const prevClose = detail.current_close_at;
    setLoading(true);
    try {
      await api.submitBid(selectedRfqId, payload);
      const updated = await api.getRfq(selectedRfqId);
      setDetail(updated);
      if (updated.current_close_at !== prevClose) {
        setNotice(
          `Quote submitted! Trigger condition met — auction close time extended to ${formatDateTime(updated.current_close_at)}.`
        );
      } else {
        setNotice('Quote submitted successfully.');
      }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to submit bid');
    } finally {
      setLoading(false);
    }
  }

  function applySupplierPreset(presetId: string) {
    if (presetId === 'SUP-001') {
      setSupplierId('SUP-001');
      setSupplierName('Maersk Global Logistics');
      setCarrierName('Maersk Line');
    } else if (presetId === 'SUP-002') {
      setSupplierId('SUP-002');
      setSupplierName('MSC Mediterranean Freight');
      setCarrierName('MSC');
    } else if (presetId === 'SUP-003') {
      setSupplierId('SUP-003');
      setSupplierName('CMA CGM Freight Services');
      setCarrierName('CMA CGM');
    } else if (presetId === 'SUP-004') {
      setSupplierId('SUP-004');
      setSupplierName('Hapag-Lloyd Express');
      setCarrierName('Hapag-Lloyd');
    }
  }

  const computedPreviewTotal =
    (Number(freightCharges) || 0) + (Number(originCharges) || 0) + (Number(destinationCharges) || 0);

  return (
    <div className="app-shell">
      <header className="top-header">
        <div>
          <h1 className="brand-title">British Auction RFQ System</h1>
          <p className="brand-subtitle">
            Transparent Supplier Bidding with Anti-Sniping Time Extensions &amp; Forced Close Rules
          </p>
        </div>
        <div className="nav-actions">
          <button
            type="button"
            className={view === 'LIST' ? 'btn' : 'btn-outline'}
            onClick={() => {
              setError(null);
              setNotice(null);
              setView('LIST');
            }}
          >
            Auction Listing
          </button>
          <button
            type="button"
            className={view === 'CREATE' ? 'btn' : 'btn-outline'}
            onClick={openCreateView}
          >
            + Create RFQ
          </button>
          <button
            type="button"
            className="btn-outline"
            onClick={handleSeedDemo}
            disabled={loading}
          >
            Load Sample Auctions
          </button>
        </div>
      </header>

      {error && <div className="alert-error">{error}</div>}
      {notice && <div className="alert-success">{notice}</div>}

      {/* VIEW 1: AUCTION LISTING PAGE */}
      {view === 'LIST' && (
        <section className="panel">
          <div className="panel-header">
            <h2 className="panel-title">All British Auctions ({rfqs.length})</h2>
            <span className="form-hint">Auto-refreshing every 3 seconds</span>
          </div>

          {rfqs.length === 0 ? (
            <div style={{ padding: '24px 0', textAlign: 'center' }}>
              <p style={{ marginBottom: '12px' }}>
                No British Auctions exist yet. Click <strong>Load Sample Auctions</strong> to generate active demo auctions or create a new RFQ.
              </p>
              <button type="button" className="btn" onClick={handleSeedDemo} disabled={loading}>
                Load Sample Auctions
              </button>
            </div>
          ) : (
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>RFQ Reference / Name</th>
                    <th>Current Lowest Bid (L1)</th>
                    <th>Current Bid Close Time</th>
                    <th>Forced Close Time</th>
                    <th>Time Remaining</th>
                    <th>Auction Status</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {rfqs.map((r) => (
                    <tr key={r.id}>
                      <td>
                        <div style={{ fontWeight: 700 }}>{r.reference_id}</div>
                        <div style={{ fontSize: '12px', color: 'var(--muted)' }}>{r.name}</div>
                      </td>
                      <td style={{ fontWeight: 700 }}>
                        {r.current_lowest_bid !== null ? `$${r.current_lowest_bid.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}` : 'No bids yet'}
                      </td>
                      <td>
                        <div>{formatDateTime(r.current_close_at)}</div>
                        {r.current_close_at !== r.bid_close_at && (
                          <div className="form-hint">Orig: {formatDateTime(r.bid_close_at)}</div>
                        )}
                      </td>
                      <td>{formatDateTime(r.forced_close_at)}</td>
                      <td style={{ fontWeight: 600 }}>
                        {r.status === 'ACTIVE'
                          ? formatCountdown(r.current_close_at, nowMs)
                          : '—'}
                      </td>
                      <td>
                        <span className={statusBadgeClass(r.status)}>{r.status.replace('_', ' ')}</span>
                      </td>
                      <td>
                        <div style={{ display: 'flex', gap: '6px' }}>
                          <button
                            type="button"
                            className="btn btn-small"
                            onClick={() => openDetailView(r.id)}
                          >
                            View &amp; Bid
                          </button>
                          <button
                            type="button"
                            className="btn-danger"
                            onClick={() => handleDeleteRfq(r.id, r.reference_id)}
                          >
                            Delete
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      )}

      {/* VIEW 2: CREATE RFQ FORM */}
      {view === 'CREATE' && (
        <section className="panel">
          <div className="panel-header">
            <h2 className="panel-title">Create New British Auction RFQ</h2>
            <span className="form-hint">Rule: Forced Bid Close Time must be later than Bid Close Time</span>
          </div>

          <form onSubmit={handleCreateRfq}>
            <div className="form-grid" style={{ marginBottom: '18px' }}>
              <div className="form-group">
                <label>RFQ Reference ID *</label>
                <input
                  type="text"
                  required
                  value={refId}
                  onChange={(e) => setRefId(e.target.value)}
                  placeholder="e.g. RFQ-2026-101"
                />
              </div>

              <div className="form-group">
                <label>RFQ Name / Lane Description *</label>
                <input
                  type="text"
                  required
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="e.g. Mumbai to Rotterdam 40ft FCL"
                />
              </div>

              <div className="form-group">
                <label>Pickup / Service Date *</label>
                <input
                  type="datetime-local"
                  required
                  value={pickupDate}
                  onChange={(e) => setPickupDate(e.target.value)}
                />
              </div>
            </div>

            <div className="form-grid" style={{ marginBottom: '18px' }}>
              <div className="form-group">
                <label>Bid Start Date &amp; Time *</label>
                <input
                  type="datetime-local"
                  required
                  value={bidStart}
                  onChange={(e) => setBidStart(e.target.value)}
                />
                <span className="form-hint">Set slightly in the past to start ACTIVE immediately</span>
              </div>

              <div className="form-group">
                <label>Bid Close Date &amp; Time *</label>
                <input
                  type="datetime-local"
                  required
                  value={bidClose}
                  onChange={(e) => setBidClose(e.target.value)}
                />
                <span className="form-hint">Initial auction close time before extensions</span>
              </div>

              <div className="form-group">
                <label>Forced Bid Close Date &amp; Time *</label>
                <input
                  type="datetime-local"
                  required
                  value={forcedClose}
                  onChange={(e) => setForcedClose(e.target.value)}
                />
                <span className="form-hint">Hard ceiling; auction never extends beyond this time</span>
              </div>
            </div>

            <div
              style={{
                borderTop: '1px solid var(--border)',
                paddingTop: '14px',
                marginBottom: '18px',
              }}
            >
              <h3 style={{ margin: '0 0 12px 0', fontSize: '14px', color: 'var(--accent)' }}>
                British Auction Extension Configuration
              </h3>
              <div className="form-grid">
                <div className="form-group">
                  <label>Trigger Window (X Minutes) *</label>
                  <input
                    type="number"
                    min={1}
                    required
                    value={windowMin}
                    onChange={(e) => setWindowMin(Number(e.target.value))}
                  />
                  <span className="form-hint">
                    Monitors activity in the last X minutes before close
                  </span>
                </div>

                <div className="form-group">
                  <label>Extension Duration (Y Minutes) *</label>
                  <input
                    type="number"
                    min={1}
                    required
                    value={extMin}
                    onChange={(e) => setExtMin(Number(e.target.value))}
                  />
                  <span className="form-hint">
                    Minutes added to close time when triggered
                  </span>
                </div>

                <div className="form-group">
                  <label>Extension Trigger Rule *</label>
                  <select
                    value={triggerType}
                    onChange={(e) => setTriggerType(e.target.value as TriggerType)}
                  >
                    <option value="BID_RECEIVED">
                      a) Bid Received in Last X Minutes
                    </option>
                    <option value="ANY_RANK_CHANGE">
                      b) Any Supplier Rank Change in Last X Minutes
                    </option>
                    <option value="L1_CHANGE">
                      c) Lowest Bidder (L1) Rank Change in Last X Minutes
                    </option>
                  </select>
                </div>
              </div>
            </div>

            <div style={{ display: 'flex', gap: '10px' }}>
              <button type="submit" className="btn" disabled={loading}>
                {loading ? 'Creating...' : 'Create British Auction RFQ'}
              </button>
              <button
                type="button"
                className="btn-outline"
                onClick={() => setView('LIST')}
              >
                Cancel
              </button>
            </div>
          </form>
        </section>
      )}

      {/* VIEW 3: AUCTION DETAILS & QUOTE SUBMISSION PAGE */}
      {view === 'DETAIL' && (
        <div>
          {!detail ? (
            <div className="panel">Loading auction details...</div>
          ) : (
            <>
              {/* Overview & Config Header */}
              <section className="panel">
                <div className="panel-header">
                  <div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                      <h2 className="panel-title">
                        {detail.reference_id} — {detail.name}
                      </h2>
                      <span className={statusBadgeClass(detail.status)}>
                        {detail.status.replace('_', ' ')}
                      </span>
                    </div>
                    <div className="form-hint" style={{ marginTop: '4px' }}>
                      RFQ UUID: {detail.id} | Pickup Date: {formatDateTime(detail.pickup_date)}
                    </div>
                  </div>
                  <div style={{ display: 'flex', gap: '8px' }}>
                    <button
                      type="button"
                      className="btn-outline btn-small"
                      onClick={() => setView('LIST')}
                    >
                      &larr; Back to Listing
                    </button>
                    <button
                      type="button"
                      className="btn-danger"
                      onClick={() => handleDeleteRfq(detail.id, detail.reference_id)}
                    >
                      Delete RFQ
                    </button>
                  </div>
                </div>

                <div className="meta-grid">
                  <div className="meta-box">
                    <div className="meta-label">Original Bid Close Time</div>
                    <div className="meta-value">{formatDateTime(detail.bid_close_at)}</div>
                  </div>
                  <div className="meta-box">
                    <div className="meta-label">Current Bid Close Time</div>
                    <div className="meta-value">
                      {formatDateTime(detail.current_close_at)}
                    </div>
                    {detail.status === 'ACTIVE' && (
                      <div className="form-hint">
                        Closes in: <strong>{formatCountdown(detail.current_close_at, nowMs)}</strong>
                      </div>
                    )}
                  </div>
                  <div className="meta-box">
                    <div className="meta-label">Forced Bid Close Time (Hard Cap)</div>
                    <div className="meta-value">{formatDateTime(detail.forced_close_at)}</div>
                  </div>
                  <div className="meta-box">
                    <div className="meta-label">Trigger Window (X) / Extension (Y)</div>
                    <div className="meta-value">
                      X = {detail.config.trigger_window_minutes} min | Y = +
                      {detail.config.extension_minutes} min
                    </div>
                  </div>
                  <div className="meta-box">
                    <div className="meta-label">Extension Trigger Policy</div>
                    <div className="meta-value" style={{ fontSize: '13px' }}>
                      {triggerLabel(detail.config.trigger_type)}
                    </div>
                  </div>
                </div>
              </section>

              <div className="details-grid">
                {/* LEFT COLUMN: SUPPLIER BIDS & RANKINGS */}
                <div>
                  <section className="panel">
                    <div className="panel-header">
                      <h3 className="panel-title">
                        Supplier Bids &amp; Rankings (Sorted by Price)
                      </h3>
                      <span className="form-hint">
                        Total Bids: {detail.bids.length}
                      </span>
                    </div>

                    {detail.bids.length === 0 ? (
                      <p className="form-hint">
                        No quotes submitted yet. Use the Quote Submission form to place the first bid.
                      </p>
                    ) : (
                      <div className="table-wrap">
                        <table>
                          <thead>
                            <tr>
                              <th>Rank</th>
                              <th>Supplier / Carrier</th>
                              <th>Charge Breakdown</th>
                              <th>Total Price</th>
                              <th>Transit / Validity</th>
                              <th>Submitted At</th>
                            </tr>
                          </thead>
                          <tbody>
                            {detail.bids.map((b) => (
                              <tr key={b.id}>
                                <td>
                                  <span
                                    className={
                                      b.rank === 1
                                        ? 'rank-pill rank-l1'
                                        : 'rank-pill'
                                    }
                                  >
                                    L{b.rank}
                                  </span>
                                  {!b.is_best_for_supplier && (
                                    <div className="form-hint" style={{ marginTop: '2px' }}>
                                      Earlier bid
                                    </div>
                                  )}
                                </td>
                                <td>
                                  <div style={{ fontWeight: 700 }}>{b.supplier_name}</div>
                                  <div className="form-hint">
                                    ID: {b.supplier_id} | Carrier: {b.carrier_name}
                                  </div>
                                </td>
                                <td style={{ fontSize: '12px' }}>
                                  Freight: ${b.freight_charges.toFixed(2)}
                                  <br />
                                  Origin: ${b.origin_charges.toFixed(2)} | Dest: $
                                  {b.destination_charges.toFixed(2)}
                                </td>
                                <td style={{ fontWeight: 700, fontSize: '14px' }}>
                                  ${b.total_price.toLocaleString(undefined, {
                                    minimumFractionDigits: 2,
                                    maximumFractionDigits: 2,
                                  })}
                                </td>
                                <td style={{ fontSize: '12px' }}>
                                  {b.transit_time_days} days
                                  <br />
                                  Valid: {b.quote_validity}
                                </td>
                                <td style={{ fontSize: '12px' }}>
                                  {formatDateTime(b.submitted_at)}
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    )}
                  </section>

                  {/* ACTIVITY LOG */}
                  <section className="panel">
                    <div className="panel-header">
                      <h3 className="panel-title">
                        Auction Activity &amp; Extension Log
                      </h3>
                      <span className="form-hint">
                        Audit trail of bids, extensions &amp; reasons
                      </span>
                    </div>

                    {detail.events.length === 0 ? (
                      <p className="form-hint">No activity recorded yet.</p>
                    ) : (
                      <ul className="event-list">
                        {detail.events.map((ev, idx) => (
                          <li
                            key={ev.id || idx}
                            className={
                              ev.event_type === 'EXTENDED'
                                ? 'event-item event-item-extended'
                                : 'event-item'
                            }
                          >
                            <div className="event-top">
                              <span>
                                {ev.event_type === 'EXTENDED'
                                  ? 'TIME EXTENDED'
                                  : 'BID SUBMITTED'}
                              </span>
                              <span>{formatDateTime(ev.created_at)}</span>
                            </div>
                            <div className="event-reason">
                              {ev.reason || 'Bid recorded.'}
                            </div>
                            {ev.event_type === 'EXTENDED' && (
                              <div className="form-hint" style={{ marginTop: '4px' }}>
                                Close time moved from{' '}
                                <strong>{formatDateTime(ev.old_close_at)}</strong>{' '}
                                &rarr;{' '}
                                <strong>{formatDateTime(ev.new_close_at)}</strong>
                              </div>
                            )}
                          </li>
                        ))}
                      </ul>
                    )}
                  </section>
                </div>

                {/* RIGHT COLUMN: QUOTE SUBMISSION FORM */}
                <div>
                  <section className="panel">
                    <div className="panel-header">
                      <h3 className="panel-title">Submit Supplier Quote</h3>
                      <span className="form-hint">
                        {detail.status === 'ACTIVE'
                          ? 'Auction is ACTIVE'
                          : `Bidding disabled (${detail.status})`}
                      </span>
                    </div>

                    <div style={{ marginBottom: '12px' }}>
                      <div className="form-hint" style={{ marginBottom: '6px' }}>
                        Quick-fill supplier preset for rapid multi-supplier testing:
                      </div>
                      <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
                        {['SUP-001', 'SUP-002', 'SUP-003', 'SUP-004'].map((preset) => (
                          <button
                            key={preset}
                            type="button"
                            className="btn-outline btn-small"
                            onClick={() => applySupplierPreset(preset)}
                          >
                            {preset}
                          </button>
                        ))}
                      </div>
                    </div>

                    <form onSubmit={handleSubmitBid}>
                      <div className="form-grid" style={{ marginBottom: '12px' }}>
                        <div className="form-group">
                          <label>Supplier ID *</label>
                          <input
                            type="text"
                            required
                            value={supplierId}
                            onChange={(e) => setSupplierId(e.target.value)}
                          />
                        </div>
                        <div className="form-group">
                          <label>Supplier Name *</label>
                          <input
                            type="text"
                            required
                            value={supplierName}
                            onChange={(e) => setSupplierName(e.target.value)}
                          />
                        </div>
                      </div>

                      <div className="form-grid" style={{ marginBottom: '12px' }}>
                        <div className="form-group">
                          <label>Carrier Name *</label>
                          <input
                            type="text"
                            required
                            value={carrierName}
                            onChange={(e) => setCarrierName(e.target.value)}
                          />
                        </div>
                        <div className="form-group">
                          <label>Transit Time (Days) *</label>
                          <input
                            type="number"
                            min={1}
                            required
                            value={transitDays}
                            onChange={(e) => setTransitDays(e.target.value)}
                          />
                        </div>
                      </div>

                      <div className="form-grid" style={{ marginBottom: '12px' }}>
                        <div className="form-group">
                          <label>Freight Charges ($) *</label>
                          <input
                            type="number"
                            step="0.01"
                            min={0}
                            required
                            value={freightCharges}
                            onChange={(e) => setFreightCharges(e.target.value)}
                          />
                        </div>
                        <div className="form-group">
                          <label>Origin Charges ($) *</label>
                          <input
                            type="number"
                            step="0.01"
                            min={0}
                            required
                            value={originCharges}
                            onChange={(e) => setOriginCharges(e.target.value)}
                          />
                        </div>
                        <div className="form-group">
                          <label>Destination Charges ($) *</label>
                          <input
                            type="number"
                            step="0.01"
                            min={0}
                            required
                            value={destinationCharges}
                            onChange={(e) => setDestinationCharges(e.target.value)}
                          />
                        </div>
                      </div>

                      <div className="form-grid" style={{ marginBottom: '14px' }}>
                        <div className="form-group">
                          <label>Validity of Quote *</label>
                          <input
                            type="date"
                            required
                            value={quoteValidity}
                            onChange={(e) => setQuoteValidity(e.target.value)}
                          />
                        </div>
                        <div className="form-group">
                          <label>Computed Total Price (Server-Verified)</label>
                          <input
                            type="text"
                            disabled
                            value={`$${computedPreviewTotal.toFixed(2)}`}
                          />
                        </div>
                      </div>

                      <button
                        type="submit"
                        className="btn"
                        style={{ width: '100%' }}
                        disabled={loading || detail.status !== 'ACTIVE'}
                      >
                        {detail.status !== 'ACTIVE'
                          ? `Bidding Closed (${detail.status})`
                          : loading
                          ? 'Submitting Quote...'
                          : 'Submit Quote'}
                      </button>
                    </form>
                  </section>
                </div>
              </div>
            </>
          )}
        </div>
      )}
    </div>
  );
}
