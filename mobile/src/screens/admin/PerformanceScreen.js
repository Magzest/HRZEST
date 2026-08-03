import React, { useState, useEffect } from "react";
import {
  SafeAreaView,
  ScrollView,
  StyleSheet,
  View,
  Text,
  TouchableOpacity,
  RefreshControl,
  ActivityIndicator,
} from "react-native";
import { DrawerActions } from "@react-navigation/native";
import { LinearGradient } from "expo-linear-gradient";
import { Ionicons } from "@expo/vector-icons";
import THEME from "../../constants/theme";
import AdminHeader from "../../components/admin/AdminHeader";
import AdminSearchBar from "../../components/admin/AdminSearchBar";
import SaasFilterSheet from "../../components/common/SaasFilterSheet";

export default function PerformanceScreen({ navigation }) {
  const [search, setSearch] = useState("");
  const [selectedStatus, setSelectedStatus] = useState("All");
  const [selectedSort, setSelectedSort] = useState("Rating (High-Low)");
  const [filterModalVisible, setFilterModalVisible] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [loading, setLoading] = useState(false);

  const [reviews, setReviews] = useState([
    {
      id: "1",
      employeeName: "Sarah Jenkins",
      role: "Senior Software Engineer",
      rating: 4.8,
      status: "Completed",
      lastReview: "Q2 2026",
      goalsMet: "95%",
    },
    {
      id: "2",
      employeeName: "Alex Rivera",
      role: "Product Manager",
      rating: 4.5,
      status: "In Progress",
      lastReview: "Q2 2026",
      goalsMet: "88%",
    },
    {
      id: "3",
      employeeName: "Michael Chen",
      role: "QA Lead",
      rating: 4.2,
      status: "Pending Review",
      lastReview: "Q1 2026",
      goalsMet: "82%",
    },
    {
      id: "4",
      employeeName: "Emily Wong",
      role: "UX Designer",
      rating: 4.9,
      status: "Completed",
      lastReview: "Q2 2026",
      goalsMet: "98%",
    },
  ]);

  const onRefresh = () => {
    setRefreshing(true);
    setTimeout(() => setRefreshing(false), 800);
  };

  const hasActiveFilter = selectedStatus !== "All" || selectedSort !== "Rating (High-Low)";

  const statuses = ["All", "Completed", "In Progress", "Pending Review"];
  const sortOptions = ["Rating (High-Low)", "Rating (Low-High)", "Name (A-Z)"];

  const filteredReviews = reviews
    .filter((r) => {
      const matchesSearch =
        r.employeeName.toLowerCase().includes(search.toLowerCase()) ||
        r.role.toLowerCase().includes(search.toLowerCase());
      const matchesStatus =
        selectedStatus === "All" || r.status === selectedStatus;
      return matchesSearch && matchesStatus;
    })
    .sort((a, b) => {
      if (selectedSort === "Rating (Low-High)") return a.rating - b.rating;
      if (selectedSort === "Name (A-Z)") return a.employeeName.localeCompare(b.employeeName);
      return b.rating - a.rating;
    });

  return (
    <LinearGradient
      colors={["#F8FAFC", "#F1F5F9", "#E2E8F0"]}
      style={styles.container}
    >
      <SafeAreaView style={{ flex: 1 }}>
        <AdminHeader
          title="Performance & KPIs"
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
          {/* Summary Hero Card */}
          <View style={styles.heroCard}>
            <View style={styles.heroHeader}>
              <View>
                <Text style={styles.heroSub}>Performance Cycle 2026</Text>
                <Text style={styles.heroTitle}>Company Avg Rating: 4.6 ★</Text>
              </View>
              <View style={styles.heroIconBadge}>
                <Ionicons name="trending-up" size={28} color="#FFFFFF" />
              </View>
            </View>
            <View style={styles.heroStatsRow}>
              <View style={styles.heroStatItem}>
                <Text style={styles.heroStatValue}>84%</Text>
                <Text style={styles.heroStatLabel}>Reviews Done</Text>
              </View>
              <View style={styles.heroStatDivider} />
              <View style={styles.heroStatItem}>
                <Text style={styles.heroStatValue}>91%</Text>
                <Text style={styles.heroStatLabel}>Goal Completion</Text>
              </View>
              <View style={styles.heroStatDivider} />
              <View style={styles.heroStatItem}>
                <Text style={styles.heroStatValue}>12</Text>
                <Text style={styles.heroStatLabel}>Top Performers</Text>
              </View>
            </View>
          </View>

          {/* Search */}
          <AdminSearchBar
            value={search}
            onChangeText={setSearch}
            placeholder="Search employee performance..."
            onFilterPress={() => setFilterModalVisible(true)}
            hasActiveFilter={hasActiveFilter}
            onClear={() => setSearch("")}
          />

          <View style={styles.sectionHeader}>
            <Text style={styles.sectionTitle}>Employee Reviews</Text>
            <Text style={styles.sectionBadge}>
              {filteredReviews.length} Records
            </Text>
          </View>

          {/* Review List */}
          {filteredReviews.map((item) => (
            <View key={item.id} style={styles.reviewCard}>
              <View style={styles.cardTop}>
                <View style={styles.avatarCircle}>
                  <Text style={styles.avatarText}>
                    {item.employeeName.charAt(0)}
                  </Text>
                </View>
                <View style={{ flex: 1, marginLeft: 12 }}>
                  <Text style={styles.empName}>{item.employeeName}</Text>
                  <Text style={styles.empRole}>{item.role}</Text>
                </View>
                <View style={styles.ratingBadge}>
                  <Ionicons name="star" size={14} color="#F59E0B" />
                  <Text style={styles.ratingText}>{item.rating}</Text>
                </View>
              </View>

              <View style={styles.cardDivider} />

              <View style={styles.cardDetailsRow}>
                <View>
                  <Text style={styles.detailLabel}>Goals Met</Text>
                  <Text style={styles.detailValue}>{item.goalsMet}</Text>
                </View>
                <View>
                  <Text style={styles.detailLabel}>Cycle</Text>
                  <Text style={styles.detailValue}>{item.lastReview}</Text>
                </View>
                <View>
                  <Text style={styles.detailLabel}>Status</Text>
                  <View
                    style={[
                      styles.statusTag,
                      item.status === "Completed"
                        ? styles.statusCompleted
                        : styles.statusProgress,
                    ]}
                  >
                    <Text
                      style={[
                        styles.statusText,
                        item.status === "Completed"
                          ? styles.statusTextCompleted
                          : styles.statusTextProgress,
                      ]}
                    >
                      {item.status}
                    </Text>
                  </View>
                </View>
              </View>
            </View>
          ))}

          <View style={{ height: 100 }} />
        </ScrollView>

        {/* Professional SaaS Filter Modal */}
        <SaasFilterSheet
          visible={filterModalVisible}
          title="Filter Performance Reviews"
          statusOptions={statuses}
          selectedStatus={selectedStatus}
          onSelectStatus={setSelectedStatus}
          sortOptions={sortOptions}
          selectedSort={selectedSort}
          onSelectSort={setSelectedSort}
          onApply={() => setFilterModalVisible(false)}
          onReset={() => {
            setSelectedStatus("All");
            setSelectedSort("Rating (High-Low)");
          }}
          onClose={() => setFilterModalVisible(false)}
        />
      </SafeAreaView>
    </LinearGradient>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1 },
  content: { paddingHorizontal: 20, paddingTop: 10 },
  heroCard: {
    backgroundColor: "#173B8C",
    borderRadius: 24,
    padding: 20,
    marginBottom: 18,
    elevation: 4,
    shadowColor: "#000",
    shadowOpacity: 0.1,
    shadowRadius: 10,
  },
  heroHeader: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: 20,
  },
  heroSub: { color: "rgba(255,255,255,0.7)", fontSize: 13, fontWeight: "600" },
  heroTitle: { color: "#FFFFFF", fontSize: 20, fontWeight: "800", marginTop: 4 },
  heroIconBadge: {
    width: 48,
    height: 48,
    borderRadius: 24,
    backgroundColor: "rgba(255,255,255,0.15)",
    justifyContent: "center",
    alignItems: "center",
  },
  heroStatsRow: {
    flexDirection: "row",
    justifyContent: "space-around",
    alignItems: "center",
    paddingTop: 12,
    borderTopWidth: 1,
    borderTopColor: "rgba(255,255,255,0.15)",
  },
  heroStatItem: { alignItems: "center" },
  heroStatValue: { color: "#FFFFFF", fontSize: 18, fontWeight: "800" },
  heroStatLabel: { color: "rgba(255,255,255,0.7)", fontSize: 11, marginTop: 2 },
  heroStatDivider: { width: 1, height: 28, backgroundColor: "rgba(255,255,255,0.15)" },
  sectionHeader: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginTop: 18,
    marginBottom: 12,
  },
  sectionTitle: { fontSize: 18, fontWeight: "800", color: "#0F172A" },
  sectionBadge: { fontSize: 13, fontWeight: "700", color: "#173B8C" },
  reviewCard: {
    backgroundColor: "#FFFFFF",
    borderRadius: 20,
    padding: 16,
    marginBottom: 12,
    elevation: 2,
    shadowColor: "#000",
    shadowOpacity: 0.04,
    shadowRadius: 8,
    borderWidth: 1,
    borderColor: "#E2E8F0",
  },
  cardTop: { flexDirection: "row", alignItems: "center" },
  avatarCircle: {
    width: 44,
    height: 44,
    borderRadius: 22,
    backgroundColor: "#EEF4FF",
    justifyContent: "center",
    alignItems: "center",
  },
  avatarText: { fontSize: 18, fontWeight: "800", color: "#173B8C" },
  empName: { fontSize: 16, fontWeight: "700", color: "#0F172A" },
  empRole: { fontSize: 13, color: "#64748B", marginTop: 2 },
  ratingBadge: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: "#FEF3C7",
    paddingHorizontal: 10,
    paddingVertical: 5,
    borderRadius: 14,
  },
  ratingText: { marginLeft: 4, fontSize: 14, fontWeight: "800", color: "#B45309" },
  cardDivider: { height: 1, backgroundColor: "#F1F5F9", marginVertical: 12 },
  cardDetailsRow: { flexDirection: "row", justifyContent: "space-between", alignItems: "center" },
  detailLabel: { fontSize: 11, color: "#94A3B8", fontWeight: "600" },
  detailValue: { fontSize: 14, fontWeight: "700", color: "#0F172A", marginTop: 2 },
  statusTag: { paddingHorizontal: 10, paddingVertical: 4, borderRadius: 12, marginTop: 2 },
  statusCompleted: { backgroundColor: "#DCFCE7" },
  statusProgress: { backgroundColor: "#E0F2FE" },
  statusText: { fontSize: 11, fontWeight: "700" },
  statusTextCompleted: { color: "#166534" },
  statusTextProgress: { color: "#075985" },
});
