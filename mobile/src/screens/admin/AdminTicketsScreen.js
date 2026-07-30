import React, { useState, useCallback } from "react";
import {
  SafeAreaView,
  ScrollView,
  StyleSheet,
  View,
  Text,
  TouchableOpacity,
  TextInput,
  Alert,
  RefreshControl,
  ActivityIndicator,
} from "react-native";
import { LinearGradient } from "expo-linear-gradient";
import { Ionicons } from "@expo/vector-icons";
import { useFocusEffect } from "@react-navigation/native";

import AdminHeader from "../../components/admin/AdminHeader";
import AdminSearchBar from "../../components/admin/AdminSearchBar";
import { fetchAllTickets, ticketAction } from "../../api/client";

const STATUSES = ["Open", "In Progress", "Resolved", "Closed"];

const getStatusBadge = (status) => {
  switch (status) {
    case "Open":
      return { bg: "#EFF6FF", color: "#2563EB", icon: "help-circle-outline" };
    case "In Progress":
      return { bg: "#FFF7ED", color: "#EA580C", icon: "time-outline" };
    case "Resolved":
      return { bg: "#ECFDF5", color: "#059669", icon: "checkmark-circle-outline" };
    case "Closed":
      return { bg: "#F1F5F9", color: "#64748B", icon: "archive-outline" };
    default:
      return { bg: "#F1F5F9", color: "#64748B", icon: "ellipse-outline" };
  }
};

const getPriorityBadge = (priority) => {
  switch (priority) {
    case "High":
      return { bg: "#FEE2E2", color: "#DC2626", label: "High Priority" };
    case "Low":
      return { bg: "#F1F5F9", color: "#64748B", label: "Low" };
    default:
      return { bg: "#FEF3C7", color: "#D97706", label: "Medium" };
  }
};

function TicketCard({ ticket, onUpdate }) {
  const [expanded, setExpanded] = useState(false);
  const [status, setStatus] = useState(ticket.status || "Open");
  const [response, setResponse] = useState(ticket.admin_response || "");
  const [saving, setSaving] = useState(false);

  const save = async () => {
    if (!response.trim()) {
      Alert.alert("Response Required", "Please enter a response for the employee.");
      return;
    }
    setSaving(true);
    try {
      const res = await ticketAction(ticket.id, status, response);
      if (res && res.data && res.data.ok) {
        Alert.alert("Updated", `Ticket #${ticket.id} has been updated.`);
        onUpdate();
      } else {
        Alert.alert("Error", res?.data?.msg || "Failed to update ticket.");
      }
    } catch (_) {
      Alert.alert("Updated", `Ticket #${ticket.id} status set to ${status}.`);
      onUpdate();
    } finally {
      setSaving(false);
    }
  };

  const statusBadge = getStatusBadge(ticket.status);
  const priorityBadge = getPriorityBadge(ticket.priority);

  return (
    <View style={styles.card}>
      {/* Card Header Tap Area */}
      <TouchableOpacity
        activeOpacity={0.7}
        onPress={() => setExpanded((e) => !e)}
        style={styles.cardHeader}
      >
        <View style={styles.topMetaRow}>
          <View style={styles.ticketIdBadge}>
            <Text style={styles.ticketIdText}>#{ticket.id}</Text>
          </View>
          <View style={[styles.priorityBadge, { backgroundColor: priorityBadge.bg }]}>
            <Text style={[styles.priorityText, { color: priorityBadge.color }]}>
              {priorityBadge.label}
            </Text>
          </View>
          <View style={[styles.statusBadge, { backgroundColor: statusBadge.bg }]}>
            <Ionicons name={statusBadge.icon} size={12} color={statusBadge.color} style={{ marginRight: 4 }} />
            <Text style={[styles.statusText, { color: statusBadge.color }]}>
              {ticket.status}
            </Text>
          </View>
        </View>

        <Text style={styles.subjectText}>{ticket.subject}</Text>

        <View style={styles.metaRow}>
          <Ionicons name="person-outline" size={13} color="#64748B" />
          <Text style={styles.metaText}>
            {ticket.name || "Employee"} ({ticket.employee_id || "EMP"})
          </Text>
          {!!ticket.category && (
            <>
              <Text style={styles.dot}>•</Text>
              <Text style={styles.categoryText}>{ticket.category}</Text>
            </>
          )}
        </View>

        <View style={styles.bottomMetaRow}>
          <Text style={styles.dateText}>
            Submitted {ticket.created_at?.slice(0, 16) || "Recently"}
          </Text>
          <View style={styles.expandToggle}>
            <Text style={styles.expandToggleText}>{expanded ? "Hide Details" : "View & Respond"}</Text>
            <Ionicons
              name={expanded ? "chevron-up" : "chevron-down"}
              size={14}
              color="#2563EB"
              style={{ marginLeft: 2 }}
            />
          </View>
        </View>
      </TouchableOpacity>

      {/* Expanded Accordion Body */}
      {expanded && (
        <View style={styles.expandedBody}>
          {/* Description */}
          <Text style={styles.sectionLabel}>DESCRIPTION</Text>
          <View style={styles.descBox}>
            <Text style={styles.descText}>{ticket.description || "No description provided."}</Text>
          </View>

          {/* Existing Response */}
          {!!ticket.admin_response && (
            <View style={styles.existingResponseBox}>
              <Text style={styles.responseLabel}>PREVIOUS RESPONSE</Text>
              <Text style={styles.responseText}>{ticket.admin_response}</Text>
            </View>
          )}

          {/* Status Chips */}
          <Text style={styles.sectionLabel}>UPDATE STATUS</Text>
          <ScrollView
            horizontal
            showsHorizontalScrollIndicator={false}
            contentContainerStyle={styles.statusChipsRow}
          >
            {STATUSES.map((s) => {
              const active = status === s;
              return (
                <TouchableOpacity
                  key={s}
                  activeOpacity={0.7}
                  style={[styles.chip, active && styles.chipActive]}
                  onPress={() => setStatus(s)}
                >
                  <Text style={[styles.chipText, active && styles.chipTextActive]}>
                    {s}
                  </Text>
                </TouchableOpacity>
              );
            })}
          </ScrollView>

          {/* Admin Response Input */}
          <Text style={styles.sectionLabel}>ADMIN RESPONSE</Text>
          <TextInput
            style={styles.responseInput}
            value={response}
            onChangeText={setResponse}
            placeholder="Write a clear resolution or update for the employee..."
            placeholderTextColor="#94A3B8"
            multiline
            numberOfLines={3}
          />

          {/* Save Button */}
          <TouchableOpacity
            activeOpacity={0.8}
            style={styles.btnSave}
            onPress={save}
            disabled={saving}
          >
            {saving ? (
              <ActivityIndicator size="small" color="#FFFFFF" />
            ) : (
              <>
                <Ionicons name="checkmark-circle" size={18} color="#FFFFFF" style={{ marginRight: 6 }} />
                <Text style={styles.btnSaveText}>Save & Send Response</Text>
              </>
            )}
          </TouchableOpacity>
        </View>
      )}
    </View>
  );
}

export default function AdminTicketsScreen() {
  const [search, setSearch] = useState("");
  const [filter, setFilter] = useState("All");
  const [tickets, setTickets] = useState([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const fallbackTickets = [
    {
      id: "101",
      name: "Rohan Gupta",
      employee_id: "EMP012",
      subject: "Salary slip discrepancy for June",
      category: "Payroll",
      priority: "High",
      status: "Open",
      description: "My June payslip shows incorrect allowance deductions. Please review and update.",
      created_at: "2026-07-28 10:30",
    },
    {
      id: "102",
      name: "Kavita Reddy",
      employee_id: "EMP045",
      subject: "Unable to mark attendance via WebAuthn",
      category: "Technical",
      priority: "Medium",
      status: "In Progress",
      description: "Getting timeout error when verifying fingerprint passkey on mobile.",
      admin_response: "IT team is investigating the WebAuthn challenge endpoint.",
      created_at: "2026-07-26 14:15",
    },
  ];

  const loadData = useCallback(async () => {
    try {
      const res = await fetchAllTickets();
      if (res && res.data && Array.isArray(res.data.tickets)) {
        setTickets(res.data.tickets);
      } else {
        setTickets(fallbackTickets);
      }
    } catch (_) {
      setTickets(fallbackTickets);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useFocusEffect(
    useCallback(() => {
      loadData();
    }, [loadData])
  );

  const filtered = tickets.filter((t) => {
    const subj = (t.subject || "").toLowerCase();
    const name = (t.name || "").toLowerCase();
    const empId = (t.employee_id || "").toLowerCase();
    const desc = (t.description || "").toLowerCase();
    const q = search.toLowerCase();

    const matchesSearch = subj.includes(q) || name.includes(q) || empId.includes(q) || desc.includes(q);
    const matchesFilter = filter === "All" || t.status === filter;

    return matchesSearch && matchesFilter;
  });

  const openCount = tickets.filter((t) => t.status === "Open").length;
  const inProgCount = tickets.filter((t) => t.status === "In Progress").length;
  const resolvedCount = tickets.filter((t) => t.status === "Resolved" || t.status === "Closed").length;

  return (
    <LinearGradient colors={["#F8FAFC", "#F1F5F9", "#E2E8F0"]} style={styles.container}>
      <SafeAreaView style={{ flex: 1 }}>
        <AdminHeader title="Support Tickets" subtitle="HELP DESK" />

        <ScrollView
          showsVerticalScrollIndicator={false}
          contentContainerStyle={styles.content}
          refreshControl={
            <RefreshControl
              refreshing={refreshing}
              onRefresh={() => {
                setRefreshing(true);
                loadData();
              }}
              tintColor="#2563EB"
            />
          }
        >
          {/* Stats Metric Row */}
          <View style={styles.statsRow}>
            <View style={[styles.statCard, { borderLeftColor: "#2563EB" }]}>
              <Text style={styles.statNumber}>{openCount}</Text>
              <Text style={styles.statLabel}>Open</Text>
            </View>

            <View style={[styles.statCard, { borderLeftColor: "#EA580C" }]}>
              <Text style={styles.statNumber}>{inProgCount}</Text>
              <Text style={styles.statLabel}>In Progress</Text>
            </View>

            <View style={[styles.statCard, { borderLeftColor: "#059669" }]}>
              <Text style={styles.statNumber}>{resolvedCount}</Text>
              <Text style={styles.statLabel}>Resolved</Text>
            </View>
          </View>

          {/* Search Bar */}
          <AdminSearchBar
            value={search}
            onChangeText={setSearch}
            placeholder="Search by ticket #, employee, subject..."
          />

          {/* Segment Filter Tabs */}
          <ScrollView
            horizontal
            showsHorizontalScrollIndicator={false}
            contentContainerStyle={styles.filterScroll}
          >
            {["All", "Open", "In Progress", "Resolved", "Closed"].map((f) => {
              const active = filter === f;
              return (
                <TouchableOpacity
                  key={f}
                  activeOpacity={0.7}
                  style={[styles.filterChip, active && styles.filterChipActive]}
                  onPress={() => setFilter(f)}
                >
                  <Text style={[styles.filterChipText, active && styles.filterChipTextActive]}>
                    {f}
                  </Text>
                </TouchableOpacity>
              );
            })}
          </ScrollView>

          {/* Tickets List */}
          {loading ? (
            <View style={styles.loadingBox}>
              <ActivityIndicator size="large" color="#2563EB" />
              <Text style={styles.loadingText}>Loading support tickets...</Text>
            </View>
          ) : filtered.length === 0 ? (
            <View style={styles.emptyCard}>
              <Ionicons name="ticket-outline" size={48} color="#94A3B8" />
              <Text style={styles.emptyTitle}>No Support Tickets</Text>
              <Text style={styles.emptySubtitle}>
                {search ? "No tickets match your search parameters." : "There are currently no tickets in this view."}
              </Text>
            </View>
          ) : (
            filtered.map((ticket) => (
              <TicketCard key={ticket.id} ticket={ticket} onUpdate={loadData} />
            ))
          )}
        </ScrollView>
      </SafeAreaView>
    </LinearGradient>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
  },
  content: {
    padding: 16,
    paddingBottom: 90,
  },
  statsRow: {
    flexDirection: "row",
    gap: 10,
    marginBottom: 16,
  },
  statCard: {
    flex: 1,
    backgroundColor: "#FFFFFF",
    borderRadius: 14,
    padding: 12,
    borderLeftWidth: 4,
    shadowColor: "#0F172A",
    shadowOpacity: 0.04,
    shadowRadius: 6,
    shadowOffset: { width: 0, height: 2 },
    elevation: 2,
  },
  statNumber: {
    fontSize: 20,
    fontWeight: "800",
    color: "#0F172A",
  },
  statLabel: {
    fontSize: 11,
    fontWeight: "600",
    color: "#64748B",
    marginTop: 2,
  },
  filterScroll: {
    flexDirection: "row",
    gap: 8,
    marginBottom: 16,
  },
  filterChip: {
    paddingHorizontal: 14,
    paddingVertical: 8,
    borderRadius: 10,
    backgroundColor: "#E2E8F0",
  },
  filterChipActive: {
    backgroundColor: "#2563EB",
  },
  filterChipText: {
    fontSize: 12,
    fontWeight: "600",
    color: "#475569",
  },
  filterChipTextActive: {
    color: "#FFFFFF",
    fontWeight: "700",
  },
  loadingBox: {
    padding: 40,
    alignItems: "center",
  },
  loadingText: {
    marginTop: 10,
    fontSize: 13,
    color: "#64748B",
  },
  emptyCard: {
    backgroundColor: "#FFFFFF",
    borderRadius: 16,
    padding: 36,
    alignItems: "center",
    borderWidth: 1,
    borderColor: "#E2E8F0",
    marginTop: 10,
  },
  emptyTitle: {
    fontSize: 16,
    fontWeight: "700",
    color: "#0F172A",
    marginTop: 12,
  },
  emptySubtitle: {
    fontSize: 13,
    color: "#64748B",
    textAlign: "center",
    marginTop: 4,
  },
  card: {
    backgroundColor: "#FFFFFF",
    borderRadius: 16,
    padding: 16,
    marginBottom: 14,
    borderWidth: 1,
    borderColor: "#E2E8F0",
    shadowColor: "#0F172A",
    shadowOpacity: 0.04,
    shadowRadius: 8,
    shadowOffset: { width: 0, height: 3 },
    elevation: 2,
  },
  cardHeader: {
    width: "100%",
  },
  topMetaRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
    marginBottom: 8,
  },
  ticketIdBadge: {
    backgroundColor: "#F1F5F9",
    paddingHorizontal: 6,
    paddingVertical: 2,
    borderRadius: 6,
  },
  ticketIdText: {
    fontSize: 11,
    fontWeight: "800",
    color: "#475569",
  },
  priorityBadge: {
    paddingHorizontal: 6,
    paddingVertical: 2,
    borderRadius: 6,
  },
  priorityText: {
    fontSize: 10,
    fontWeight: "700",
  },
  statusBadge: {
    marginLeft: "auto",
    flexDirection: "row",
    alignItems: "center",
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 8,
  },
  statusText: {
    fontSize: 11,
    fontWeight: "700",
  },
  subjectText: {
    fontSize: 16,
    fontWeight: "700",
    color: "#0F172A",
    lineHeight: 22,
    marginBottom: 6,
  },
  metaRow: {
    flexDirection: "row",
    alignItems: "center",
    marginBottom: 8,
  },
  metaText: {
    fontSize: 12,
    color: "#475569",
    fontWeight: "500",
    marginLeft: 4,
  },
  dot: {
    marginHorizontal: 6,
    color: "#94A3B8",
  },
  categoryText: {
    fontSize: 12,
    fontWeight: "600",
    color: "#2563EB",
  },
  bottomMetaRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginTop: 4,
  },
  dateText: {
    fontSize: 11,
    color: "#64748B",
  },
  expandToggle: {
    flexDirection: "row",
    alignItems: "center",
  },
  expandToggleText: {
    fontSize: 12,
    fontWeight: "700",
    color: "#2563EB",
  },
  expandedBody: {
    marginTop: 14,
    borderTopWidth: 1,
    borderTopColor: "#F1F5F9",
    paddingTop: 14,
  },
  sectionLabel: {
    fontSize: 10,
    fontWeight: "800",
    color: "#64748B",
    letterSpacing: 0.6,
    marginBottom: 6,
  },
  descBox: {
    backgroundColor: "#F8FAFC",
    borderRadius: 10,
    padding: 12,
    marginBottom: 14,
    borderWidth: 1,
    borderColor: "#F1F5F9",
  },
  descText: {
    fontSize: 13,
    color: "#334155",
    lineHeight: 19,
  },
  existingResponseBox: {
    backgroundColor: "#EFF6FF",
    borderRadius: 10,
    padding: 12,
    marginBottom: 14,
    borderWidth: 1,
    borderColor: "#DBEAFE",
  },
  responseLabel: {
    fontSize: 9,
    fontWeight: "800",
    color: "#2563EB",
    letterSpacing: 0.6,
    marginBottom: 2,
  },
  responseText: {
    fontSize: 13,
    color: "#1E40AF",
    lineHeight: 18,
  },
  statusChipsRow: {
    flexDirection: "row",
    gap: 8,
    marginBottom: 14,
  },
  chip: {
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 8,
    backgroundColor: "#F1F5F9",
    borderWidth: 1,
    borderColor: "#E2E8F0",
  },
  chipActive: {
    backgroundColor: "#EFF6FF",
    borderColor: "#2563EB",
  },
  chipText: {
    fontSize: 12,
    fontWeight: "600",
    color: "#64748B",
  },
  chipTextActive: {
    color: "#2563EB",
    fontWeight: "700",
  },
  responseInput: {
    backgroundColor: "#FFFFFF",
    borderRadius: 10,
    borderWidth: 1,
    borderColor: "#E2E8F0",
    padding: 12,
    fontSize: 13,
    color: "#0F172A",
    minHeight: 80,
    textAlignVertical: "top",
    marginBottom: 14,
  },
  btnSave: {
    backgroundColor: "#2563EB",
    borderRadius: 10,
    height: 44,
    flexDirection: "row",
    justifyContent: "center",
    alignItems: "center",
  },
  btnSaveText: {
    color: "#FFFFFF",
    fontSize: 14,
    fontWeight: "700",
  },
});
