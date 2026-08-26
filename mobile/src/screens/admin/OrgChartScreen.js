import React, { useState, useEffect, useCallback } from "react";
import {
  SafeAreaView,
  ScrollView,
  StyleSheet,
  View,
  Text,
  RefreshControl,
  ActivityIndicator,
} from "react-native";
import { DrawerActions } from "@react-navigation/native";
import { LinearGradient } from "expo-linear-gradient";
import { Ionicons } from "@expo/vector-icons";
import THEME from "../../constants/theme";
import AdminHeader from "../../components/admin/AdminHeader";
import { fetchOrgChart, fetchDashboard } from "../../api/client";

// Real manager_id-based reporting hierarchy via /api/org_chart (Bearer
// twin of blueprints/admin_views.py's session-only /api/org_chart_data),
// not the flattened department grouping this screen used to fall back to.
export default function OrgChartScreen({ navigation }) {
  const [refreshing, setRefreshing] = useState(false);
  const [loading, setLoading] = useState(true);
  const [tree, setTree] = useState([]);
  const [total, setTotal] = useState(0);
  const [companyName, setCompanyName] = useState("");

  const load = useCallback(async () => {
    try {
      const [chartRes, dashRes] = await Promise.all([
        fetchOrgChart(),
        fetchDashboard().catch(() => null),
      ]);
      if (chartRes?.data?.ok) {
        setTree(chartRes.data.tree || []);
        setTotal(chartRes.data.total || 0);
      }
      setCompanyName(dashRes?.data?.company_name || "");
    } catch (_) {
      setTree([]);
      setTotal(0);
    }
  }, []);

  useEffect(() => {
    setLoading(true);
    load().finally(() => setLoading(false));
  }, [load]);

  const onRefresh = async () => {
    setRefreshing(true);
    await load();
    setRefreshing(false);
  };

  return (
    <LinearGradient
      colors={["#F8FAFC", "#F1F5F9", "#E2E8F0"]}
      style={styles.container}
    >
      <SafeAreaView style={{ flex: 1 }}>
        <AdminHeader
          title="Organization Chart"
          onMenu={() => navigation.dispatch(DrawerActions.openDrawer())}
        />

        <ScrollView
          showsVerticalScrollIndicator={false}
          contentContainerStyle={styles.content}
          refreshControl={
            <RefreshControl
              refreshing={refreshing}
              onRefresh={onRefresh}
              colors={[THEME.colors.primary]}
            />
          }
        >
          {/* Company Summary Box */}
          <View style={styles.execCard}>
            <View style={styles.execBadge}>
              <Text style={styles.execBadgeText}>ORGANIZATION</Text>
            </View>
            <Text style={styles.execName}>{companyName || "Your Company"}</Text>
            <View style={styles.execStats}>
              <Text style={styles.execStatsText}>
                {total} Total Staff • {tree.length} Reporting Root{tree.length !== 1 ? "s" : ""}
              </Text>
            </View>
          </View>

          <View style={styles.treeConnector} />

          <View style={styles.sectionHeader}>
            <Text style={styles.sectionTitle}>Reporting Hierarchy</Text>
          </View>

          {loading ? (
            <ActivityIndicator size="large" color="#173B8C" style={{ marginTop: 20 }} />
          ) : tree.length === 0 ? (
            <View style={styles.emptyCard}>
              <Ionicons name="git-network-outline" size={40} color="#94A3B8" />
              <Text style={styles.emptyText}>No employees found yet.</Text>
            </View>
          ) : (
            tree.map((node) => <OrgNode key={node.id} node={node} depth={0} />)
          )}

          <View style={{ height: 100 }} />
        </ScrollView>
      </SafeAreaView>
    </LinearGradient>
  );
}

function OrgNode({ node, depth }) {
  return (
    <View style={{ marginLeft: depth * 18 }}>
      <View style={styles.nodeCard}>
        <View style={styles.nodeIconBadge}>
          <Ionicons name="person" size={18} color="#173B8C" />
        </View>
        <View style={{ flex: 1, marginLeft: 12 }}>
          <Text style={styles.nodeName}>{node.name}</Text>
          <Text style={styles.nodeRole}>
            {node.role}{node.department ? ` • ${node.department}` : ""}
          </Text>
        </View>
        {node.children?.length > 0 && (
          <View style={styles.countBadge}>
            <Text style={styles.countText}>{node.children.length} report{node.children.length !== 1 ? "s" : ""}</Text>
          </View>
        )}
      </View>
      {node.children?.map((child) => (
        <OrgNode key={child.id} node={child} depth={depth + 1} />
      ))}
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1 },
  content: { paddingHorizontal: 20, paddingTop: 10 },
  execCard: {
    backgroundColor: "#173B8C",
    borderRadius: 24,
    padding: 20,
    alignItems: "center",
    elevation: 4,
  },
  execBadge: {
    backgroundColor: "rgba(255,255,255,0.15)",
    paddingHorizontal: 12,
    paddingVertical: 4,
    borderRadius: 12,
    marginBottom: 8,
  },
  execBadgeText: { color: "#93C5FD", fontSize: 10, fontWeight: "800", letterSpacing: 1 },
  execName: { color: "#FFFFFF", fontSize: 16, fontWeight: "800" },
  execStats: { marginTop: 14, paddingTop: 10, borderTopWidth: 1, borderTopColor: "rgba(255,255,255,0.15)" },
  execStatsText: { color: "#FFFFFF", fontSize: 12, fontWeight: "600" },
  treeConnector: {
    width: 2,
    height: 24,
    backgroundColor: "#CBD5E1",
    alignSelf: "center",
    marginVertical: 4,
  },
  sectionHeader: { marginBottom: 12 },
  sectionTitle: { fontSize: 14, fontWeight: "800", color: "#0F172A" },
  emptyCard: {
    backgroundColor: "#FFFFFF",
    borderRadius: 20,
    padding: 32,
    alignItems: "center",
    borderWidth: 1,
    borderColor: "#E2E8F0",
  },
  emptyText: { marginTop: 10, fontSize: 13, color: "#64748B", fontWeight: "600" },
  nodeCard: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: "#FFFFFF",
    borderRadius: 16,
    padding: 12,
    marginBottom: 10,
    borderWidth: 1,
    borderColor: "#E2E8F0",
  },
  nodeIconBadge: {
    width: 36,
    height: 36,
    borderRadius: 18,
    backgroundColor: "#EEF4FF",
    justifyContent: "center",
    alignItems: "center",
  },
  nodeName: { fontSize: 13, fontWeight: "700", color: "#0F172A" },
  nodeRole: { fontSize: 11, color: "#64748B", marginTop: 2, fontWeight: "600" },
  countBadge: {
    backgroundColor: "#F1F5F9",
    paddingHorizontal: 10,
    paddingVertical: 5,
    borderRadius: 12,
  },
  countText: { fontSize: 11, fontWeight: "700", color: "#334155" },
});
