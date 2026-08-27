import React, { useState, useCallback } from "react";
import {
  SafeAreaView,
  ScrollView,
  View,
  Text,
  TextInput,
  TouchableOpacity,
  ActivityIndicator,
  RefreshControl,
} from "react-native";

import { StyleSheet } from "react-native";
import { useFocusEffect } from "@react-navigation/native";
import { Ionicons } from "@expo/vector-icons";

import ProfileHeader from "../../components/profile/ProfileHeader";
import EmptyState from "../../components/ui/EmptyState";
import LoadingSkeleton from "../../components/ui/LoadingSkeleton";

import EmployeePerformanceCard from "../../components/performance/EmployeePerformanceCard";

import { useAuth } from "../../store/AuthContext";
import { fetchEmployeeProfile, fetchMyPerformance, submitMyPerformanceComment } from "../../api/client";

function ReviewCard({ review, onSubmitComment, submittingId }) {
  const [comment, setComment] = useState(review.employee_comment || "");
  const isSubmitting = submittingId === review.id;

  return (
    <View style={styles.reviewCard}>
      <View style={styles.reviewHeader}>
        <Text style={styles.reviewQuarter}>Q{review.quarter} {review.year}</Text>
        <View style={styles.ratingPill}>
          <Ionicons name="star" size={12} color="#F59E0B" />
          <Text style={styles.ratingPillText}>{review.overall_rating_label}</Text>
        </View>
      </View>
      <Text style={styles.reviewStatus}>{review.status}</Text>

      {review.kpis.length > 0 && (
        <View style={styles.kpiSection}>
          {review.kpis.map((kpi, idx) => (
            <View key={idx} style={styles.kpiRow}>
              <View style={{ flex: 1 }}>
                <Text style={styles.kpiTitle}>{kpi.kpi_title}</Text>
                {!!kpi.target && <Text style={styles.kpiTarget}>Target: {kpi.target}{kpi.achievement ? ` · Achieved: ${kpi.achievement}` : ""}</Text>}
              </View>
              <Text style={styles.kpiRating}>{kpi.rating || 0}/5</Text>
            </View>
          ))}
        </View>
      )}

      {!!review.reviewer_feedback && (
        <View style={styles.feedbackBox}>
          <Text style={styles.feedbackLabel}>MANAGER FEEDBACK</Text>
          <Text style={styles.feedbackText}>{review.reviewer_feedback}</Text>
        </View>
      )}

      <Text style={styles.commentLabel}>YOUR COMMENT</Text>
      <TextInput
        style={styles.commentInput}
        placeholder="Add your comment on this review..."
        value={comment}
        onChangeText={setComment}
        multiline
      />
      <TouchableOpacity
        style={styles.commentBtn}
        onPress={() => onSubmitComment(review.id, comment)}
        disabled={isSubmitting}
      >
        {isSubmitting ? (
          <ActivityIndicator color="#FFFFFF" size="small" />
        ) : (
          <Text style={styles.commentBtnText}>{review.employee_comment ? "Update Comment" : "Submit Comment"}</Text>
        )}
      </TouchableOpacity>
    </View>
  );
}

export default function PerformanceScreen() {
  const { user } = useAuth();
  const [profile, setProfile] = useState(null);
  const [reviews, setReviews] = useState([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [submittingId, setSubmittingId] = useState(null);

  const load = useCallback(async () => {
    try {
      const [profRes, perfRes] = await Promise.all([fetchEmployeeProfile(), fetchMyPerformance()]);
      if (profRes?.data?.ok) setProfile(profRes.data.profile);
      if (perfRes?.data?.ok) setReviews(perfRes.data.reviews || []);
    } catch (_) {
      // Fall back to whatever identity AuthContext already has.
    }
  }, []);

  useFocusEffect(
    useCallback(() => {
      let cancelled = false;
      (async () => {
        setLoading(true);
        if (!cancelled) await load();
        if (!cancelled) setLoading(false);
      })();
      return () => { cancelled = true; };
    }, [load])
  );

  const onRefresh = async () => {
    setRefreshing(true);
    await load();
    setRefreshing(false);
  };

  const handleSubmitComment = async (reviewId, comment) => {
    setSubmittingId(reviewId);
    try {
      const res = await submitMyPerformanceComment(reviewId, comment);
      if (res?.data?.ok) {
        await load();
      }
    } catch (_) {
      // review keeps its previous comment state on failure
    }
    setSubmittingId(null);
  };

  const name = profile?.name || user?.name || "Employee";
  const employeeId = profile?.employee_id || user?.employeeId || "-";
  const designation = profile?.role || "-";
  const department = profile?.department || "-";

  return (
    <SafeAreaView style={styles.container}>
      <ProfileHeader
        title="My Performance"
        showBack={false}
      />

      <ScrollView
        showsVerticalScrollIndicator={false}
        contentContainerStyle={styles.content}
        refreshControl={
          <RefreshControl refreshing={refreshing} onRefresh={onRefresh} />
        }
      >
        {loading ? (
          <>
            <LoadingSkeleton height={110} radius={24} style={{ marginBottom: 22 }} />
            <LoadingSkeleton height={140} radius={24} />
          </>
        ) : (
          <>
            <EmployeePerformanceCard
              name={name}
              designation={designation}
              department={department}
              employeeId={employeeId}
            />

            {reviews.length === 0 ? (
              <EmptyState
                icon="stats-chart-outline"
                title="No performance reviews yet"
                description="Your quarterly review will appear here once your manager or HR admin creates one."
              />
            ) : (
              reviews.map((review) => (
                <ReviewCard
                  key={review.id}
                  review={review}
                  onSubmitComment={handleSubmitComment}
                  submittingId={submittingId}
                />
              ))
            )}
          </>
        )}
      </ScrollView>
    </SafeAreaView>
  );
}
const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: "#F8FAFC",
  },

  content: {
    paddingHorizontal: 18,
    paddingBottom: 120,
    paddingTop: 18,
  },

  reviewCard: {
    backgroundColor: "#FFFFFF",
    borderRadius: 18,
    padding: 16,
    marginBottom: 14,
    borderWidth: 1,
    borderColor: "#E2E8F0",
  },
  reviewHeader: { flexDirection: "row", justifyContent: "space-between", alignItems: "center" },
  reviewQuarter: { fontSize: 15, fontWeight: "800", color: "#0F172A" },
  ratingPill: {
    flexDirection: "row",
    alignItems: "center",
    gap: 4,
    backgroundColor: "#FFFBEB",
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 20,
  },
  ratingPillText: { fontSize: 11.5, fontWeight: "700", color: "#B45309" },
  reviewStatus: { fontSize: 11.5, color: "#64748B", fontWeight: "600", marginTop: 3 },
  kpiSection: { marginTop: 14, borderTopWidth: 1, borderTopColor: "#F1F5F9", paddingTop: 10 },
  kpiRow: { flexDirection: "row", alignItems: "center", paddingVertical: 6 },
  kpiTitle: { fontSize: 13, fontWeight: "700", color: "#0F172A" },
  kpiTarget: { fontSize: 11.5, color: "#94A3B8", marginTop: 2 },
  kpiRating: { fontSize: 13, fontWeight: "800", color: "#173B8C" },
  feedbackBox: { backgroundColor: "#EEF4FF", borderRadius: 12, padding: 12, marginTop: 12 },
  feedbackLabel: { fontSize: 10.5, fontWeight: "800", color: "#173B8C", letterSpacing: 0.4 },
  feedbackText: { fontSize: 13, color: "#1E293B", marginTop: 6, lineHeight: 18 },
  commentLabel: { fontSize: 10.5, fontWeight: "800", color: "#64748B", letterSpacing: 0.4, marginTop: 14 },
  commentInput: {
    backgroundColor: "#F8FAFC",
    borderWidth: 1,
    borderColor: "#E2E8F0",
    borderRadius: 10,
    padding: 10,
    marginTop: 6,
    fontSize: 13,
    color: "#0F172A",
    minHeight: 60,
    textAlignVertical: "top",
  },
  commentBtn: {
    backgroundColor: "#173B8C",
    borderRadius: 10,
    paddingVertical: 11,
    alignItems: "center",
    marginTop: 10,
  },
  commentBtnText: { color: "#FFFFFF", fontWeight: "700", fontSize: 13 },
});
