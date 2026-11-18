export type TriggerType = 'BID_RECEIVED' | 'ANY_RANK_CHANGE' | 'L1_CHANGE';

export interface AuctionConfig {
  trigger_window_minutes: number;
  extension_minutes: number;
  trigger_type: TriggerType;
}

export interface RfqSummary {
  id: string;
  reference_id: string;
  name: string;
  current_lowest_bid: number | null;
  bid_start_at: string;
  bid_close_at: string;
  current_close_at: string;
  forced_close_at: string;
  pickup_date: string;
  status: 'SCHEDULED' | 'ACTIVE' | 'CLOSED' | 'FORCE_CLOSED';
}

export interface BidOut {
  id: string;
  supplier_id: string;
  supplier_name: string;
  carrier_name: string;
  freight_charges: number;
  origin_charges: number;
  destination_charges: number;
  total_price: number;
  transit_time_days: number;
  quote_validity: string;
  submitted_at: string;
  rank: number | null;
  is_best_for_supplier?: boolean;
}

export interface AuctionEventOut {
  id?: string | null;
  event_type: 'BID_SUBMITTED' | 'EXTENDED' | 'CLOSED' | 'FORCE_CLOSED';
  bid_id: string | null;
  old_close_at: string | null;
  new_close_at: string | null;
  reason: string | null;
  created_at: string;
}

export interface RfqDetail {
  id: string;
  reference_id: string;
  name: string;
  bid_start_at: string;
  bid_close_at: string;
  current_close_at: string;
  forced_close_at: string;
  pickup_date: string;
  status: 'SCHEDULED' | 'ACTIVE' | 'CLOSED' | 'FORCE_CLOSED';
  config: AuctionConfig;
  bids: BidOut[];
  events: AuctionEventOut[];
}

export interface RfqCreatePayload {
  reference_id: string;
  name: string;
  bid_start_at: string;
  bid_close_at: string;
  forced_close_at: string;
  pickup_date: string;
  config: AuctionConfig;
}

export interface BidCreatePayload {
  supplier_id: string;
  supplier_name: string;
  carrier_name: string;
  freight_charges: number;
  origin_charges: number;
  destination_charges: number;
  transit_time_days: number;
  quote_validity: string;
}
