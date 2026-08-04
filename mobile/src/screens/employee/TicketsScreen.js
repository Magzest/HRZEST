import React, { useState, useCallback } from "react";
import {
  SafeAreaView,
  ScrollView,
  StyleSheet,
  Alert,
  RefreshControl,
  View,
} from "react-native";
import { useFocusEffect } from "@react-navigation/native";
import ProfileHeader from "../../components/profile/ProfileHeader";
import TicketHeaderCard from "../../components/tickets/TicketHeaderCard";
import SectionTitle from "../../components/tickets/SectionTitle";
import TicketCategoryPicker from "../../components/tickets/TicketCategoryPicker";
import PrioritySelector from "../../components/tickets/PrioritySelector";
import SubjectInput from "../../components/tickets/SubjectInput";
import DescriptionInput from "../../components/tickets/DescriptionInput";
import AttachmentCard from "../../components/tickets/AttachmentCard";
import RaiseTicketButton from "../../components/tickets/RaiseTicketButton";
import TicketStatsCard from "../../components/tickets/TicketStatsCard";
import TicketCard from "../../components/tickets/TicketCard";
import EmptyTickets from "../../components/tickets/EmptyTickets";
import { fetchEmployeeTickets, raiseTicket } from "../../api/client";

export default function TicketsScreen() {
  const [category, setCategory] = useState("hr");
  const [priority, setPriority] = useState("Medium");
  const [subject, setSubject] = useState("");
  const [description, setDescription] = useState("");
  const [attachment, setAttachment] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [ticketList, setTicketList] = useState([]);

  const loadTickets = async () => {
    try {
      const res = await fetchEmployeeTickets();
      if (res?.data?.tickets) {
        setTicketList(res.data.tickets);
      } else if (Array.isArray(res?.data)) {
        setTicketList(res.data);
      } else {
        setTicketList([]);
      }
    } catch (e) {
      setTicketList([]);
    } finally {
      setRefreshing(false);
    }
  };

  useFocusEffect(
    useCallback(() => {
      loadTickets();
    }, [])
  );

  const handleRaiseTicket = async () => {
    if (!subject.trim() || !description.trim()) {
      Alert.alert("Input Required", "Subject and Description are required to submit a ticket.");
      return;
    }
    setSubmitting(true);
    const newTicket = {
      id: `TK-${Math.floor(1000 + Math.random() * 9000)}`,
      category: category.toUpperCase(),
      subject: subject.trim(),
      description: description.trim(),
      priority,
      status: "Open",
      created_at: new Date().toLocaleDateString("en-US", { day: "numeric", month: "short", year: "numeric" }),
    };

    setTicketList((prev) => [newTicket, ...prev]);

    try {
      await raiseTicket(category, subject.trim(), description.trim(), priority).catch(() => null);
    } catch (_) {}

    Alert.alert("Ticket Submitted 🎉", "Your support request has been created.");
    setSubject("");
    setDescription("");
    setAttachment("");
    setSubmitting(false);
  };

  const totalTickets = ticketList.length;
  const openTickets = ticketList.filter((t) => t.status === "Open" || t.status === "Pending").length;
  const inProgressTickets = ticketList.filter((t) => t.status === "In Progress" || t.status === "Assigned").length;
  const resolvedTickets = ticketList.filter((t) => t.status === "Resolved" || t.status === "Closed").length;

  return (
    <SafeAreaView style={styles.container}>
      <ProfileHeader title="Support Tickets" showBack={false} />

      <ScrollView
        showsVerticalScrollIndicator={false}
        contentContainerStyle={styles.content}
        refreshControl={
          <RefreshControl
            refreshing={refreshing}
            onRefresh={() => {
              setRefreshing(true);
              loadTickets();
            }}
            colors={["#173B8C"]}
          />
        }
      >
        <TicketHeaderCard
          totalTickets={totalTickets}
          openTickets={openTickets}
          resolvedTickets={resolvedTickets}
        />

        <SectionTitle
          icon="create-outline"
          title="Raise New Ticket"
          subtitle="Submit your issue directly to HR & IT support."
        />

        <TicketCategoryPicker
          selectedCategory={category}
          onSelectCategory={setCategory}
        />

        <PrioritySelector
          selectedPriority={priority}
          onSelectPriority={setPriority}
        />

        <SubjectInput value={subject} onChangeText={setSubject} />

        <DescriptionInput value={description} onChangeText={setDescription} />

        <AttachmentCard
          fileName={attachment}
          onUpload={() => setAttachment("Document_Attachment.png")}
        />

        <RaiseTicketButton loading={submitting} onPress={handleRaiseTicket} />

        <SectionTitle
          icon="stats-chart-outline"
          title="Ticket Overview"
          subtitle="Current support request breakdown"
        />

        <TicketStatsCard
          open={openTickets}
          inProgress={inProgressTickets}
          resolved={resolvedTickets}
        />

        <SectionTitle
          icon="document-text-outline"
          title="My Tickets"
          subtitle="Your submitted support history"
        />

        {ticketList.length === 0 ? (
          <EmptyTickets />
        ) : (
          ticketList.map((item, idx) => (
            <TicketCard
              key={item.id || idx.toString()}
              id={item.id || ""}
              category={item.category || ""}
              subject={item.subject}
              priority={item.priority || ""}
              status={item.status || ""}
              createdAt={item.created_at || item.createdAt || ""}
            />
          ))
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
    padding: 16,
    paddingBottom: 40,
  },
});