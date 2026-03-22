#!/usr/bin/env node

/**
 * Gruppo Hera CLI - Download bills from Servizi Online
 * 
 * Usage:
 *   node hera-cli.js login          - Login and cache tokens
 *   node hera-cli.js bills          - List all bills
 *   node hera-cli.js download <id>  - Download specific bill
 *   node hera-cli.js download-all   - Download all bills
 *   node hera-cli.js logout         - Clear cached tokens
 *   node hera-cli.js status         - Check authentication status
 */

const hera = require('./index');
const fs = require('fs');
const path = require('path');

/**
 * Format usage data for display with ASCII chart
 */
function formatUsageForDisplay(usageData) {
  const { list = [] } = usageData;
  
  if (list.length === 0) {
    return 'No usage data available';
  }

  let output = '\n';
  
  for (const usage of list) {
    const period = `${usage.usageFromDate ? new Date(usage.usageFromDate).toLocaleDateString() : 'N/A'} - ${usage.usageToDate ? new Date(usage.usageToDate).toLocaleDateString() : 'N/A'}`;
    const readType = usage.readType || 'N/A';
    const totalUsage = usage.totalUsage ? `${usage.totalUsage.toFixed(2)} kWh` : 'N/A';
    const averageUsage = usage.averageUsage ? `${usage.averageUsage.toFixed(2)} kWh/giorno` : 'N/A';
    
    output += `Period: ${period}\n`;
    output += `Read Type: ${readType}\n`;
    output += `Total Usage: ${totalUsage}\n`;
    output += `Average Usage: ${averageUsage}\n`;
    
    // Display F1/F2/F3 bands if available (reads is an array of objects)
    if (usage.reads && usage.reads.length > 0) {
      output += '\nConsumption by band:\n';
      output += '─'.repeat(40) + '\n';
      
      // Convert reads array to object for easier access
      const readsObj = {};
      for (const read of usage.reads) {
        readsObj[read.type] = read;
      }
      
      // Calculate max value for scaling (handle all zeros)
      const values = [readsObj.F0?.value || 0, readsObj.F1?.value || 0, readsObj.F2?.value || 0, readsObj.F3?.value || 0];
      const maxValue = Math.max(...values, 1);
      
      for (const [band, data] of Object.entries(readsObj)) {
        const value = data.value || 0;
        const percentage = data.percentage || 0;
        
        // Create bar chart (max 30 chars) - handle 0 values
        const barLength = maxValue > 0 ? Math.round((value / maxValue) * 30) : 0;
        const bar = '█'.repeat(Math.max(0, barLength)) + '░'.repeat(Math.max(0, 30 - barLength));
        
        output += `${band}: ${bar} ${value.toFixed(2)} kWh (${percentage.toFixed(1)}%)\n`;
      }
      output += '─'.repeat(40) + '\n';
    }
    
    output += '\n' + '='.repeat(60) + '\n\n';
  }
  
  return output;
}

const COMMANDS = {
  login: {
    desc: 'Login with credentials',
    usage: 'node hera-cli.js login',
    handler: async () => {
      const readline = require('readline');
      const rl = readline.createInterface({
        input: process.stdin,
        output: process.stdout
      });

      const question = (q) => new Promise(resolve => rl.question(q, resolve));

      try {
        const email = await question('Email: ');
        const password = await question('Password: ');
        
        console.log('Logging in...');
        await hera.login(email.trim(), password.trim());
        console.log('✓ Login successful! Session cached.');
      } catch (error) {
        console.error('✗ Login failed:', error.message);
        process.exit(1);
      } finally {
        rl.close();
      }
    }
  },

  bills: {
    desc: 'List all bills',
    usage: 'node hera-cli.js bills',
    handler: async () => {
      try {
        const bills = await hera.getBills();
        
        if (bills.length === 0) {
          console.log('No bills found or unable to parse bills from page.');
          console.log('Note: HTML parsing may need to be configured for your specific view.');
          return;
        }

        console.log(`\nFound ${bills.length} bills:\n`);
        console.log('ID'.padEnd(40), 'Date'.padEnd(15), 'Amount'.padEnd(15), 'Status');
        console.log('-'.repeat(85));
        
        for (const bill of bills) {
          const id = bill.id || bill.documentId || 'N/A';
          const date = bill.emissionDate ? new Date(bill.emissionDate).toISOString().split('T')[0] : (bill.date || bill.issueDate || 'N/A');
          const amount = bill.amount ? bill.amount.toFixed(2) + '€' : (bill.total || 'N/A');
          const status = bill.paymentStatus || 'N/A';
          
          console.log(
            id.padEnd(40),
            date.padEnd(15),
            String(amount).padEnd(15),
            status
          );
        }
        console.log();
      } catch (error) {
        console.error('✗ Failed to get bills:', error.message);
        process.exit(1);
      }
    }
  },

  download: {
    desc: 'Download a specific bill',
    usage: 'node hera-cli.js download <bill-id>',
    handler: async (args) => {
      const billId = args[0];
      
      if (!billId) {
        console.error('✗ Bill ID required');
        console.error('Usage: node hera-cli.js download <bill-id>');
        process.exit(1);
      }

      try {
        console.log(`Downloading bill ${billId}...`);
        const pdf = await hera.downloadBill(billId);
        
        const filename = `bill-${billId}.pdf`;
        fs.writeFileSync(filename, pdf);
        console.log(`✓ Downloaded: ${filename}`);
      } catch (error) {
        console.error('✗ Failed to download bill:', error.message);
        process.exit(1);
      }
    }
  },

  'download-all': {
    desc: 'Download all bills',
    usage: 'node hera-cli.js download-all',
    handler: async () => {
      try {
        const bills = await hera.getBills();
        
        if (bills.length === 0) {
          console.log('No bills to download.');
          return;
        }

        console.log(`Downloading ${bills.length} bills...\n`);
        
        for (const bill of bills) {
          const billId = bill.id || bill.documentId;
          if (!billId) continue;

          try {
            const pdf = await hera.downloadBill(billId);
            const filename = `bill-${billId}.pdf`;
            fs.writeFileSync(filename, pdf);
            console.log(`✓ ${filename}`);
          } catch (error) {
            console.error(`✗ Failed ${billId}: ${error.message}`);
          }
        }
        
        console.log('\nDone!');
      } catch (error) {
        console.error('✗ Failed:', error.message);
        process.exit(1);
      }
    }
  },

  logout: {
    desc: 'Clear cached session',
    usage: 'node hera-cli.js logout',
    handler: async () => {
      hera.logout();
    }
  },

  status: {
    desc: 'Check authentication status',
    usage: 'node hera-cli.js status',
    handler: async () => {
      const authenticated = hera.isAuthenticated();
      console.log(`Status: ${authenticated ? '✓ Logged in' : '✗ Not logged in'}`);
    }
  },

  contracts: {
    desc: 'List all contracts (electricity and gas)',
    usage: 'node hera-cli.js contracts',
    handler: async () => {
      try {
        const contracts = await hera.getContracts();
        
        if (contracts.length === 0) {
          console.log('No contracts found.');
          return;
        }

        console.log(`\nFound ${contracts.length} contracts:\n`);
        console.log('ID'.padEnd(15), 'Type'.padEnd(12), 'Status'.padEnd(12), 'Address', 'POD/PDR');
        console.log('-'.repeat(100));
        
        for (const contract of contracts) {
          const id = contract.id || 'N/A';
          const type = contract.serviceType || 'N/A';
          const status = contract.status || 'N/A';
          const address = (contract.supplyAddress || contract.deliveryAddress || 'N/A').substring(0, 35);
          const pod = contract.pod || (contract.meters?.[0]?.pod) || 'N/A';
          
          console.log(
            id.padEnd(15),
            type.padEnd(12),
            status.padEnd(12),
            address.padEnd(35),
            pod
          );
        }
        console.log();
      } catch (error) {
        console.error('✗ Failed to get contracts:', error.message);
        process.exit(1);
      }
    }
  },

  usage: {
    desc: 'Get consumption data for a contract',
    usage: 'node hera-cli.js usage <contract-id> [page]',
    handler: async (args) => {
      const contractId = args[0];
      const page = parseInt(args[1]) || 0;
      
      if (!contractId) {
        console.error('✗ Contract ID required');
        console.error('Usage: node hera-cli.js usage <contract-id> [page]');
        console.error('\nFirst run: node hera-cli.js contracts to get contract IDs');
        process.exit(1);
      }

      try {
        console.log(`Fetching usage data for contract ${contractId}...`);
        const usageData = await hera.getUsage(contractId, { pageNumber: page, pageSize: 10 });
        
        if (!usageData.list || usageData.list.length === 0) {
          console.log('No usage data available for this contract.');
          return;
        }

        console.log(formatUsageForDisplay(usageData));
        
        if (usageData.hasNext) {
          console.log(`\n⚠ More pages available. Use: node hera-cli.js usage ${contractId} ${page + 1}`);
        }
      } catch (error) {
        console.error('✗ Failed to get usage data:', error.message);
        process.exit(1);
      }
    }
  },

  'usage-export': {
    desc: 'Export usage data to Excel',
    usage: 'node hera-cli.js usage-export <contract-id> [type]',
    handler: async (args) => {
      const contractId = args[0];
      const type = (args[1] || 'ELECTRIC').toUpperCase();
      
      if (!contractId) {
        console.error('✗ Contract ID required');
        console.error('Usage: node hera-cli.js usage-export <contract-id> [ELECTRIC|GAS]');
        console.error('\nFirst run: node hera-cli.js contracts to get contract IDs');
        process.exit(1);
      }

      if (!['ELECTRIC', 'GAS'].includes(type)) {
        console.error('✗ Invalid type. Use ELECTRIC or GAS');
        process.exit(1);
      }

      try {
        console.log(`Exporting usage data for contract ${contractId} (${type})...`);
        const excelBuffer = await hera.getUsageExport(contractId, type);
        
        const filename = `usage-${contractId}-${type.toLowerCase()}.xls`;
        fs.writeFileSync(filename, excelBuffer);
        console.log(`✓ Exported: ${filename}`);
      } catch (error) {
        console.error('✗ Failed to export usage data:', error.message);
        process.exit(1);
      }
    }
  }
};

// Main CLI handler
function main() {
  const args = process.argv.slice(2);
  const command = args[0];

  if (!command || command === 'help' || command === '-h' || command === '--help') {
    console.log('\nGruppo Hera CLI - Download bills from Servizi Online\n');
    console.log('Commands:');
    for (const [name, cmd] of Object.entries(COMMANDS)) {
      console.log(`  ${name.padEnd(15)} ${cmd.desc}`);
      console.log(`                 ${cmd.usage}\n`);
    }
    console.log('Example:');
    console.log('  node hera-cli.js login');
    console.log('  node hera-cli.js bills');
    console.log('  node hera-cli.js download-all\n');
    return;
  }

  const cmd = COMMANDS[command];
  if (!cmd) {
    console.error(`✗ Unknown command: ${command}`);
    console.error('Run: node hera-cli.js help');
    process.exit(1);
  }

  cmd.handler(args.slice(1)).catch(error => {
    console.error('✗ Error:', error.message);
    process.exit(1);
  });
}

main();
