import { motion } from "framer-motion";
import {
  ArrowLeft,
  CheckCircle,
  Loader2,
  Package,
  ShieldAlert,
  ShieldCheck,
  User,
  XCircle,
} from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, useNavigate } from "react-router";
import ModalBackdrop from "../components/ModalBackdrop";
import ModalHeader from "../components/ModalHeader";
import { Badge, Button, Card, EmptyState } from "../components/ui";
import { useNotify } from "../context/NotificationContext";
import { API_BASE_URL } from "../lib/api-config";
import { getAuthToken } from "../lib/tokenStorage";
import type { ComponentItem } from "./ComponentLibrary";

export default function ComponentReview() {
  useTranslation();
  const { notify } = useNotify();
  const navigate = useNavigate();

  const [pendingItems, setPendingItems] = useState<ComponentItem[]>([]);
  const [loading, setLoading] = useState(true);

  // Review action modal states
  const [selectedItem, setSelectedItem] = useState<ComponentItem | null>(null);
  const [actionType, setActionType] = useState<"approve" | "reject" | null>(null);
  const [reviewNotes, setReviewNotes] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const fetchPending = useCallback(async () => {
    setLoading(true);
    try {
      const token = getAuthToken();
      const res = await fetch(`${API_BASE_URL}/api/v1/components/pending`, {
        headers: { ...(token ? { Authorization: `Bearer ${token}` } : {}) },
      });

      if (res.status === 403) {
        notify("error", "Admin privileges required to view review queue");
        setPendingItems([]);
        return;
      }

      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      setPendingItems(Array.isArray(data) ? data : []);
    } catch (err) {
      notify("error", "Failed to fetch pending components");
    } finally {
      setLoading(false);
    }
  }, [notify]);

  useEffect(() => {
    fetchPending();
  }, [fetchPending]);

  const handleReviewSubmit = async () => {
    if (!selectedItem || !actionType) return;
    if (actionType === "reject" && !reviewNotes.trim()) {
      notify("error", "Please provide a rejection reason for the contributor");
      return;
    }

    setSubmitting(true);
    try {
      const token = getAuthToken();
      const endpoint =
        actionType === "approve"
          ? `${API_BASE_URL}/api/v1/components/${selectedItem.id}/verify`
          : `${API_BASE_URL}/api/v1/components/${selectedItem.id}/reject`;

      const payload =
        actionType === "approve"
          ? { notes: reviewNotes.trim() || undefined }
          : { reason: reviewNotes.trim() };

      const res = await fetch(endpoint, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify(payload),
      });

      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      notify(
        "success",
        actionType === "approve"
          ? `Component "${selectedItem.name}" approved and published to catalog!`
          : `Component "${selectedItem.name}" rejected.`,
      );
      setSelectedItem(null);
      setActionType(null);
      setReviewNotes("");
      fetchPending();
    } catch (err) {
      notify("error", `Action failed: ${err instanceof Error ? err.message : "Unknown error"}`);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <motion.div
        initial={{ opacity: 0, y: 15 }}
        animate={{ opacity: 1, y: 0 }}
        className="flex items-center justify-between gap-4"
      >
        <div className="flex items-center gap-3">
          <Button
            variant="ghost"
            size="icon"
            onClick={() => navigate("/component-library")}
            icon={ArrowLeft}
          />
          <div className="p-3 rounded-2xl bg-amber-500/10 border border-amber-500/20 text-amber-400">
            <ShieldAlert className="w-7 h-7" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-2xl font-bold text-[var(--text-primary)]">
                Component Verification Queue
              </h1>
              <Badge variant="warning" size="sm">
                Dual Control
              </Badge>
            </div>
            <p className="text-sm text-[var(--text-muted)]">
              Admin review and maker-checker validation for community contributed component specifications.
            </p>
          </div>
        </div>

        <Link to="/component-library">
          <Button variant="secondary" size="sm" icon={Package}>
            Back to Library
          </Button>
        </Link>
      </motion.div>

      {/* Queue Content */}
      {loading ? (
        <div className="flex flex-col items-center justify-center py-16 gap-3">
          <Loader2 className="w-8 h-8 text-brand-400 animate-spin" />
          <p className="text-sm text-[var(--text-muted)]">Checking pending submissions...</p>
        </div>
      ) : pendingItems.length === 0 ? (
        <EmptyState
          icon={<ShieldCheck className="w-10 h-10 text-emerald-400" />}
          title="All Caught Up!"
          description="There are currently no component submissions awaiting verification."
          action={
            <Link to="/component-library">
              <Button variant="secondary" size="sm">
                Browse Catalog
              </Button>
            </Link>
          }
        />
      ) : (
        <div className="space-y-4">
          <span className="text-xs text-[var(--text-muted)] font-semibold uppercase tracking-wider">
            {pendingItems.length} Submission{pendingItems.length > 1 ? "s" : ""} Pending Review
          </span>

          {pendingItems.map((item) => (
            <Card key={item.id} padding="md">
              <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4">
                <div className="space-y-2 flex-1">
                  <div className="flex items-center gap-2 flex-wrap">
                    <Badge variant="warning">{item.type.toUpperCase()}</Badge>
                    <h3 className="text-base font-bold text-[var(--text-primary)]">{item.name}</h3>
                    {item.manufacturer && (
                      <span className="text-xs text-[var(--text-secondary)]">
                        by <strong>{item.manufacturer}</strong>
                      </span>
                    )}
                  </div>

                  <div className="flex flex-wrap items-center gap-3 text-xs text-[var(--text-secondary)]">
                    <span>
                      Category: <strong>{item.category}</strong>
                    </span>
                    {item.standards && item.standards.length > 0 && (
                      <span>
                        Standards:{" "}
                        <strong className="font-mono text-brand-400">
                          {item.standards.join(", ")}
                        </strong>
                      </span>
                    )}
                    {item.contributor_id && (
                      <span className="flex items-center gap-1 text-[var(--text-muted)]">
                        <User className="w-3.5 h-3.5" /> Submitter: {item.contributor_id}
                      </span>
                    )}
                  </div>

                  {/* Specs dump preview */}
                  {item.specs && Object.keys(item.specs).length > 0 && (
                    <div className="p-2.5 rounded-lg bg-[var(--bg-primary)] border border-[var(--border-primary)] text-xs font-mono max-h-32 overflow-y-auto">
                      <pre className="text-[var(--text-secondary)]">
                        {JSON.stringify(item.specs, null, 2)}
                      </pre>
                    </div>
                  )}

                  {item.review_notes && (
                    <p className="text-xs text-[var(--text-muted)] italic">
                      Notes: {item.review_notes}
                    </p>
                  )}
                </div>

                <div className="flex items-center gap-2 self-end lg:self-center">
                  <Button
                    variant="danger"
                    size="sm"
                    icon={XCircle}
                    onClick={() => {
                      setSelectedItem(item);
                      setActionType("reject");
                    }}
                  >
                    Reject
                  </Button>
                  <Button
                    variant="primary"
                    size="sm"
                    icon={CheckCircle}
                    onClick={() => {
                      setSelectedItem(item);
                      setActionType("approve");
                    }}
                  >
                    Verify & Approve
                  </Button>
                </div>
              </div>
            </Card>
          ))}
        </div>
      )}

      {/* Action Dialog */}
      {selectedItem && actionType && (
        <ModalBackdrop
          onClose={() => {
            setSelectedItem(null);
            setActionType(null);
          }}
        >
          <div className="bg-[var(--bg-secondary)] border border-[var(--border-primary)] rounded-2xl max-w-md w-full p-6 shadow-2xl space-y-4">
            <ModalHeader
              title={actionType === "approve" ? "Verify & Publish Component" : "Reject Submission"}
              icon={actionType === "approve" ? CheckCircle : XCircle}
              onClose={() => {
                setSelectedItem(null);
                setActionType(null);
              }}
            />
            <p className="text-xs text-[var(--text-muted)] -mt-2 mb-2 font-semibold">
              {selectedItem.name}
            </p>

            <div className="space-y-3 text-xs">
              <label htmlFor="review-decision-notes" className="block font-medium text-[var(--text-secondary)]">
                {actionType === "approve"
                  ? "Verification Notes (Optional)"
                  : "Rejection Reason (Required for Contributor)"}
              </label>
              <textarea
                id="review-decision-notes"
                rows={3}
                required={actionType === "reject"}
                value={reviewNotes}
                onChange={(e) => setReviewNotes(e.target.value)}
                placeholder={
                  actionType === "approve"
                    ? "e.g. Verified against standard table or manufacturer test sheet"
                    : "e.g. Incomplete impedance parameters or missing rated voltage"
                }
                className="w-full px-3 py-2 rounded-lg bg-[var(--bg-input)] border border-[var(--border-primary)] text-[var(--text-primary)]"
              />
            </div>

            <div className="flex justify-end gap-2 pt-3 border-t border-[var(--border-primary)]">
              <Button
                variant="ghost"
                onClick={() => {
                  setSelectedItem(null);
                  setActionType(null);
                }}
              >
                Cancel
              </Button>
              <Button
                variant={actionType === "approve" ? "primary" : "danger"}
                disabled={submitting}
                onClick={handleReviewSubmit}
              >
                {submitting
                  ? "Processing..."
                  : actionType === "approve"
                    ? "Confirm Approval"
                    : "Confirm Rejection"}
              </Button>
            </div>
          </div>
        </ModalBackdrop>
      )}
    </div>
  );
}
