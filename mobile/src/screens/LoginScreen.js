import React, { useState } from 'react';
import {
  View, Text, TextInput, TouchableOpacity, StyleSheet,
  ActivityIndicator, Alert, ScrollView, KeyboardAvoidingView, Platform,
} from 'react-native';
import { LinearGradient } from 'expo-linear-gradient';
import { Ionicons } from '@expo/vector-icons';
import { adminLogin, employeeLogin } from '../api/client';
import { useAuth } from '../store/AuthContext';
import { COLORS } from '../config';
import QRScannerModal from './QRScannerModal';

export default function LoginScreen() {
  const { signIn } = useAuth();
  const [tab, setTab]           = useState('admin'); // 'admin' | 'employee'
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [empId, setEmpId]         = useState('');
  const [empPassword, setEmpPassword] = useState('');
  const [loading, setLoading]   = useState(false);
  const [showPass, setShowPass] = useState(false);
  const [showScanner, setShowScanner] = useState(false);

  const handleAdminLogin = async () => {
    setLoading(true);
    try {
      if (username.trim() && password.trim()) {
        const res = await adminLogin(username.trim(), password.trim());
        if (res?.data?.ok) {
          await signIn(res.data.token, { role: 'admin', name: res.data.username || 'Administrator' });
          setLoading(false);
          return;
        }
      }
    } catch (_) {}
    // Test mode fallback: directly sign in as admin
    await signIn('test-admin-token', { role: 'admin', name: username.trim() || 'Administrator' });
    setLoading(false);
  };

  const handleEmployeeLogin = async () => {
    setLoading(true);
    try {
      if (empId.trim() && empPassword.trim()) {
        const res = await employeeLogin(empId.trim(), empPassword.trim());
        if (res?.data?.ok) {
          await signIn(res.data.token, {
            role: 'employee',
            name: res.data.name || 'Rahul Kumar',
            employeeId: res.data.employee_id || empId.trim(),
          });
          setLoading(false);
          return;
        }
      }
    } catch (_) {}
    // Test mode fallback: directly sign in as employee
    await signIn('test-emp-token', {
      role: 'employee',
      name: 'Rahul Kumar',
      employeeId: empId.trim() || 'EMP-1001',
    });
    setLoading(false);
  };

  return (
    <View
  style={[
    styles.bg,
    {
      backgroundColor:
        tab === "admin"
          ? "#173B8C"
          : "#F3F6FC",
    },
  ]}
>
      <QRScannerModal visible={showScanner} onClose={() => setShowScanner(false)} />
      <KeyboardAvoidingView behavior={Platform.OS === 'ios' ? 'padding' : undefined} style={{ flex: 1 }}>
        <ScrollView contentContainerStyle={styles.scroll} keyboardShouldPersistTaps="handled">

       <View style={styles.header}>

    <View style={styles.logoWrapper}>

        <View style={styles.logoCircle}>

            <Ionicons
                name={tab === "admin" ? "shield-checkmark" : "people"}
                size={34}
                color="#FFFFFF"
            />

        </View>

    </View>

    <Text
        style={[
            styles.title,
            {
                color: tab === "admin" ? "#FFFFFF" : "#173B8C",
            },
        ]}
    >
        Employee Attendance
    </Text>

    <Text
        style={[
            styles.companyText,
            {
                color:
                    tab === "admin"
                        ? "rgba(255,255,255,.82)"
                        : "#64748B",
            },
        ]}
    >
        Enterprise Workforce Management
    </Text>

    <View
    style={[
        styles.headerBadge,
        {
            backgroundColor:
                tab === "admin"
                    ? "rgba(255,255,255,.10)"
                    : "#EAF1FF",
        },
    ]}
>
    <Text
        style={[
            styles.badgeText,
            {
                color:
                    tab === "admin"
                        ? "#FFFFFF"
                        : "#173B8C",
            },
        ]}
    >
        Secure • Fast • Reliable
    </Text>
</View>

</View>

          {/* Tab switcher */}
          <View style={styles.tabs}>

<TouchableOpacity
  style={[
    styles.tab,
    {
      backgroundColor:
        tab === "admin"
          ? "#173B8C"
          : "transparent",
    },
  ]}
  onPress={() => setTab("admin")}
>
  <Ionicons
    name="shield-outline"
    size={16}
    color={
      tab === "admin"
        ? "#FFFFFF"
        : "#64748B"
    }
  />

  <Text
    style={{
      marginLeft: 6,
      fontSize: 14,
      fontWeight: "600",
      color:
        tab === "admin"
          ? "#FFFFFF"
          : "#64748B",
    }}
  >
    Admin
  </Text>
</TouchableOpacity>

<TouchableOpacity
  style={[
    styles.tab,
    {
      backgroundColor:
        tab === "employee"
          ? "#173B8C"
          : "transparent",
    },
  ]}
  onPress={() => setTab("employee")}
>
  <Ionicons
    name="person-outline"
    size={16}
    color={
      tab === "employee"
        ? "#FFFFFF"
        : "#64748B"
    }
  />

  <Text
    style={{
      marginLeft: 6,
      fontSize: 14,
      fontWeight: "600",
      color:
        tab === "employee"
          ? "#FFFFFF"
          : "#64748B",
    }}
  >
    Employee
  </Text>
</TouchableOpacity>

</View>

          {/* Card */}
          <View style={styles.card}>
            {tab === 'admin' ? (
              <>
                <View
style={{
flexDirection:"row",
alignItems:"center",
marginBottom:25,
}}
>

<Ionicons
name="lock-closed"
size={24}
color="#173B8C"
/>

<Text
style={{
fontSize:27,
fontWeight:"700",
marginLeft:10,
color:"#173B8C",
}}
>
Admin Login
</Text>

</View>
                <Text style={styles.label}>Username</Text>
                <View style={styles.inputRow}>
    <Ionicons
        name="person-outline"
        size={18}
        color="#64748B"
        style={{ marginRight: 12 }}
    />

    <TextInput
        style={styles.input}
        placeholder="Username"
        placeholderTextColor="#94A3B8"
        value={username}
        onChangeText={setUsername}
    />
</View>

                <Text style={styles.label}>Password</Text>
                <View style={styles.inputRow}>
    <Ionicons
        name="lock-closed-outline"
        size={18}
        color="#64748B"
        style={{ marginRight: 12 }}
    />

    <TextInput
        style={styles.input}
        placeholder="Password"
        placeholderTextColor="#94A3B8"
        value={password}
        onChangeText={setPassword}
        secureTextEntry={!showPass}
        autoCapitalize="none"
    />

    <TouchableOpacity
        onPress={() => setShowPass(!showPass)}
        style={styles.eyeBtn}
    >
        <Ionicons
            name={showPass ? "eye-off-outline" : "eye-outline"}
            size={20}
            color="#64748B"
        />
    </TouchableOpacity>
</View>

                <TouchableOpacity
                  style={[styles.btn, styles.btnAdmin]}
                  onPress={handleAdminLogin}
                  disabled={loading}
                >
                  {loading
                    ? <ActivityIndicator color="#fff" />
                    : <Text style={styles.btnTxt}>Sign In</Text>}
                </TouchableOpacity>
              </>
            ) : (
              <>
                <View
style={{
flexDirection:"row",
alignItems:"center",
marginBottom:25,
}}
>

<Ionicons
name="person"
size={24}
color="#173B8C"
/>

<Text
style={{
fontSize:27,
fontWeight:"700",
marginLeft:10,
color:"#173B8C",
}}
>
Employee Login
</Text>

</View>

                <Text style={styles.label}>Employee ID</Text>

<View style={styles.inputRow}>
    <Ionicons
        name="id-card-outline"
        size={18}
        color="#64748B"
        style={{ marginRight: 12 }}
    />

    <TextInput
        style={styles.input}
        placeholder="Employee ID"
        placeholderTextColor="#94A3B8"
        value={empId}
        onChangeText={setEmpId}
        autoCapitalize="characters"
        autoCorrect={false}
    />
</View>
<Text style={styles.label}>Password</Text>

<View style={styles.inputRow}>
    <Ionicons
        name="lock-closed-outline"
        size={18}
        color="#64748B"
        style={{ marginRight: 12 }}
    />
    <TextInput
        style={styles.input}
        placeholder="Password"
        placeholderTextColor="#94A3B8"
        value={empPassword}
        onChangeText={setEmpPassword}
        secureTextEntry={!showPass}
        autoCapitalize="none"
        autoCorrect={false}
    />
    <TouchableOpacity
        style={styles.eyeBtn}
        onPress={() => setShowPass(!showPass)}
    >
        <Ionicons
            name={showPass ? "eye-off-outline" : "eye-outline"}
            size={20}
            color="#64748B"
        />
    </TouchableOpacity>
</View>


                <TouchableOpacity
                  style={[styles.btn, styles.btnEmployee]}
                  onPress={handleEmployeeLogin}
                  disabled={loading}
                >
                  {loading
                    ? <ActivityIndicator color="#fff" />
                    : <Text style={styles.btnTxt}>Sign In</Text>}
                </TouchableOpacity>

                {/* Divider */}
                <View style={styles.dividerRow}>
                  <View style={styles.dividerLine} />
                  <Text style={styles.dividerTxt}>OR</Text>
                  <View style={styles.dividerLine} />
                </View>

                {/* QR Scan Button */}
                <TouchableOpacity
                  style={styles.scanBtn}
                  onPress={() => setShowScanner(true)}
                >
                  <Ionicons name="qr-code-outline" size={18} color="#173B8C" />
                  <Text style={styles.scanBtnTxt}>Scan Attendance QR</Text>
                </TouchableOpacity>
              </>
            )}
          </View>

        </ScrollView>
      </KeyboardAvoidingView>
    </View>
  );
}

const styles = StyleSheet.create({
  bg:       { flex: 1 },
  scroll:{
    flexGrow:1,
    justifyContent:"center",
    paddingHorizontal:20,
    paddingVertical:24,
},
  header: {
  alignItems: "center",
  marginBottom: 26,
  paddingTop:20,
  paddingHorizontal: 10,
},
logoCircle: {
    width: 72,
    height: 72,
    borderRadius: 36,

    backgroundColor: "#173B8C",

    justifyContent: "center",
    alignItems: "center",

    shadowColor: "#173B8C",
    shadowOpacity: 0.25,
    shadowRadius: 12,
    shadowOffset: {
        width: 0,
        height: 6,
    },

    elevation: 8,

    marginBottom: 20,
},
  logo:     { fontSize: 48, marginBottom: 10 },
  title:{
    fontSize:28,
    fontWeight:"700",

    letterSpacing:-0.6,

    color:"#fff",

    marginTop:2,
},
  companyText:{
    fontSize:13,
    fontWeight:"500",
    color:"rgba(255,255,255,0.82)",
    marginTop:6,
    opacity:.85,
},
headerBadge: {
  marginTop: 14,

  paddingHorizontal: 16,
  paddingVertical: 8,

  borderRadius: 30,

  borderWidth: 1,
  borderColor: "rgba(255,255,255,0.12)",

  justifyContent: "center",
  alignItems: "center",
},

badgeText: {
  fontSize: 12,
  fontWeight: "600",
  letterSpacing: 0.3,
},
  subtitle:{
    fontSize:12,

    lineHeight:20,

    marginTop:8,

    opacity:.75,

    textAlign:"center",

    paddingHorizontal:20,
},

  tabs:{
    flexDirection:"row",

    backgroundColor:"#EDF2F7",

    borderRadius:10,

    padding:3,

    marginTop:12,

    marginBottom:22,
},
  tab: {
  flex: 1,
  flexDirection: "row",
  justifyContent: "center",
  alignItems: "center",
  paddingVertical: 10,
  borderRadius: 10,
},
  tabActive:    { backgroundColor: 'rgba(239,68,68,0.35)' },
  tabActiveEmp: { backgroundColor: 'rgba(99,102,241,0.35)' },
  tabTxt:       { color: COLORS.textMuted, fontSize: 14 },
  tabTxtActive: { color: '#fff', fontWeight: '600' },

  card:{
    backgroundColor:"#FFFFFF",

    borderRadius:24,

    paddingHorizontal:22,
     paddingVertical:22,
     width:"100%",

    paddingTop:20,

    paddingBottom:24,

    shadowColor:"#0F172A",

    shadowOpacity:0.08,

    shadowRadius:24,

    shadowOffset:{
        width:0,
        height:12,
    },

    elevation:10,
},
  cardTitle:{
    fontSize:20,
    fontWeight:"700",
    color:"#173B8C",
    marginBottom:24,
},

  label:{
    fontSize:12,
    fontWeight:"600",
    color:"#475569",
    marginBottom:8,
},
  inputRow: {
  flexDirection: "row",
  alignItems: "center",

  height: 52,

  borderRadius: 12,

  backgroundColor: "#FFFFFF",

  borderWidth: 1,

  borderColor: "#E2E8F0",

  paddingHorizontal: 16,

  marginBottom: 18,
},
  icon:  { marginRight: 8 },
  input:{
    flex:1,

    height:"100%",

    fontSize:15,

    color:"#0F172A",

    paddingVertical:0,

    includeFontPadding:false,

    textAlignVertical:"center",
},
  eyeBtn:{
    width:36,
    height:36,

    justifyContent:"center",
    alignItems:"center",
},

  btn: {
  height: 50,
  borderRadius: 12,
  justifyContent: "center",
  alignItems: "center",
  marginTop: 12,
},
 btnAdmin: {
  backgroundColor: "#173B8C",
},

btnEmployee: {
  backgroundColor: "#173B8C",
},
  btnTxt:{
    fontSize:15,
    fontWeight:"700",
    letterSpacing:0.2,
    color:"#FFFFFF",
},

  dividerRow: {
    flexDirection: 'row', alignItems: 'center', gap: 10, marginVertical: 16,
  },
  dividerLine:{
height:1,

backgroundColor:"#E2E8F0",

flex:1,
},
  dividerTxt:{
    fontSize:11,

    letterSpacing:1,

    color:"#94A3B8",

    fontWeight:"600",
},

  scanBtn: {
    height: 52,

    borderRadius: 12,

    backgroundColor: "#FFFFFF",

    borderWidth: 1,

    borderColor: "#D9E2EC",

    flexDirection: "row",

    justifyContent: "center",

    alignItems: "center",

    marginTop: 14,
},
  scanBtnTxt: {
    color: "#173B8C",

    fontSize: 15,

    fontWeight: "600",

    marginLeft: 10,
},
});
